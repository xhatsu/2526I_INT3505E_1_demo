from flask import jsonify, make_response

def create_response(data, status_code, headers=None):
    """
    Creates a structured JSON response and allows adding custom headers.
    """
    if 200 <= status_code < 300:
        status = 'success'
    else:
        status = 'error'

    response_data = {
        'status': status,
        'data': data
    }

    json_response = jsonify(response_data)

    response = make_response(json_response, status_code)

    if headers:
        for key, value in headers.items():
            response.headers[key] = value

    return response