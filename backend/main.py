from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import JSONResponse
import db_functions
import generic_functions

app = FastAPI()
inprogress_orders= {}


@app.post("/")
async def handle_request(request: Request):
    # Retrieve the JSON data from the request
    payload = await request.json()

    # Extract the necessary information from the payload
    # based on the structure of the WebhookRequest from Dialogflow
    intent = payload['queryResult']['intent']['displayName']
    parameters = payload['queryResult']['parameters']
    output_contexts = payload['queryResult']['outputContexts']


    session_id = generic_functions.extract_session_id(output_contexts[0]['name'])

    intent_handler_dict = {
        'new.order': new_order,
        'order.add - context: ongoing-order': add_to_order,
        'order.remove - context: ongoing-order': remove_from_order,
        'order.complete - context: ongoing-order': complete_order,
        'track.order - context: ongoing-tracking': track_order
    }


    return intent_handler_dict[intent](parameters, session_id)

def new_order(parameters: dict, session_id: str):
    del inprogress_orders[session_id]
def add_to_order(parameters: dict, session_id: str):


    food_items = parameters["food-item"]
    quantities = parameters["number"]

    if len(food_items) != len(quantities):
        fulfillment_text = "Sorry I didn't understand. Can you please specify food items and quantities clearly?"
    else:
        fooditems_to_add = dict(zip(food_items,quantities))

        if session_id in inprogress_orders:
            fooditems_initial = inprogress_orders[session_id]
            fooditems_initial.update(fooditems_to_add)
            inprogress_orders[session_id] = fooditems_initial

        else:
            inprogress_orders[session_id] = fooditems_to_add


        food_and_quantity = generic_functions.get_food_and_quantity_from_dict(inprogress_orders[session_id])

        fulfillment_text = f"As of now, You've ordered {food_and_quantity}. Is there anything additional you'd like to include in your order?"

    return JSONResponse(content={"fulfillmentText": fulfillment_text})

def complete_order(parameters: dict, session_id: str):

    if session_id not in inprogress_orders:
        fulfillment_text = f"Sorry, I am not able to find your order. Can you place a new order, Please?"
    else:
        order = inprogress_orders[session_id]  # put this in the DB
        current_order_id = save_to_db(order)

        if current_order_id == -1:
            fulfillment_text = "Sorry, I could not process your order due to backend error.\
                                Please place a new order again"
        else:
            order_total = db_functions.get_total_order_price(current_order_id)
            fulfillment_text = f"Your order has been placed. Your order_id #{current_order_id}.Your order total is {order_total}, \
            which you can pay at the time of delivery."

        del inprogress_orders[session_id]

    return JSONResponse(content={"fulfillmentText": fulfillment_text})

def save_to_db(order: dict):
    next_order_id = db_functions.get_next_order_id()

    for food_item, quantity in order.items():
        return_code = db_functions.insert_order_item(
            food_item,
            quantity,
            next_order_id
        )

        if return_code == -1:
            return -1

    db_functions.insert_order_tracking(next_order_id, "Inprogress")
    return next_order_id

def track_order(parameters: dict, session_id: str):
    order_id = int(parameters['number'])
    order_status = db_functions.get_order_status(order_id)

    if order_status:
        fulfillment_text = f"The order status for the order id: {order_id} is: {order_status}"

    else:
        fulfillment_text = f"No order found for the order id {order_id}"

    return JSONResponse(content={"fulfillmentText": fulfillment_text})

def remove_from_order(parameters: dict, session_id: str):
    if session_id not in inprogress_orders:
        return JSONResponse(content={
            "fulfillmentText": "Sorry, I am not able to find your order. Can you place a new order, Please?"
        })

    else:
        current_order = inprogress_orders[session_id]         # {pizza:2, dosa:1}
        food_items = parameters["food-item"]                              # Remove dosa. Here dosa is the "food-item"

        removed_items = []
        not_in_order = []

        for item in food_items:
            if item not in current_order:
                not_in_order.append(item)
            else:
                removed_items.append(item)
                del current_order[item]                           # {pizza:2}

        if len(removed_items) > 0:
            fulfillment_text = f'Removed {",".join(removed_items)} from your order!'

        if len(not_in_order) > 0:
            fulfillment_text = f'Your order does not have {",".join(not_in_order)}'

        if len(current_order.keys()) == 0:
            fulfillment_text += "Your order is Empty"

        else:
            food_and_quantity = generic_functions.get_food_and_quantity_from_dict(current_order)
            fulfillment_text += f"Now your order includes : {food_and_quantity}"

    return JSONResponse(content={"fulfillmentText": fulfillment_text})


