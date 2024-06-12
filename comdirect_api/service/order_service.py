import requests
import json

class OrderService:

    def __init__(self, session, api_url):
        self.session = session
        self.api_url = api_url

    def get_dimensions(self, **kwargs):
        """
        7.1.1 Abruf Order Dimensionen
        :key instrument_id: fiters instrumentId
        :key wkn: fiters WKN
        :key isin: fiters ISIN
        :key mneomic: fiters mneomic
        :key venue_id: fiters venueId: Mit Hilfe der venueId, welche als UUID eingegeben werden muss, kann auf einen Handelsplatz gefiltert werden
        :key side: Entspricht der Geschäftsart. Filtermöglichkeiten sind BUY oder SELL
        :key order_type: fiters orderType: Enspricht dem Ordertypen (bspw. LIMIT, MARKET oder ONE_CANCELS_OTHER)
        :key type: filters type: Mittels EXCHANGE oder OFF kann unterschieden werden, ob nach einem Börsenplatz (EXCHANGE) oder einem LiveTrading Handelsplatz (OFF) gefiltert werden soll
        :return: Response object
        """
        kwargs_mapping = {
            "instrument_id": "instrumentId",
            "wkn": "wkn",          # Dokumentation ist falsch, wkn muss klein geschrieben werden!
            "isin": "isin",
            "mneomic": "mneomic",
            "venue_id": "venueId",
            "side": "side",
            "order_type": "orderType",
            "type": "type"
        }

        url = '{0}/brokerage/v3/orders/dimensions'.format(self.api_url)
        params = {}

        for arg, val in kwargs.items():
            api_arg = kwargs_mapping.get(arg)
            if api_arg is None:
                raise ValueError('Keyword argument {} is invalid'.format(arg))
            else:
                params[api_arg] = val
        # response = self.session.get(url, json=params).json()   # Das ist ein BUG!!!
        response = self.session.get(url, params=params).json()
        return response

    def get_all_orders(self, depot_id, with_instrument=False, with_executions=True, **kwargs):
        """
        7.1.2 Abruf Orders (Orderbuch)

        :param depot_id: Depot-ID
        :param with_instrument: Include instrument information. Defaults to False.
        :param with_executions: Include execution information. Defaults to True.
        :key order_status: filter by orderStatus: {"OPEN ", "EXECUTED", "SETTLED"...}
        :key venue_id: filter by venueId
        :key side: filter by side: {"BUY", "SELL"}
        :key order_type: filter by orderType
        :return: Response object
        """
        kwargs_mapping = {
            "order_status": "orderStatus",
            "venue_id": "venueId",
            "side": "side",
            "order_type": "orderType"
        }

        url = '{0}/brokerage/depots/{1}/v3/orders'.format(self.api_url, depot_id)
        params = {}

        if with_instrument:
            params['with-attr'] = 'instrument'
        if not with_executions:
            params['without-attr'] = 'executions'

        for arg, val in kwargs.items():
            api_arg = kwargs_mapping.get(arg)
            if api_arg is None:
                raise ValueError('Keyword argument {} is invalid'.format(arg))
            else:
                params[api_arg] = val

        response = self.session.get(url, params=params).json()
        return response

    def get_order(self, order_id):
        """
        7.1.3 Abruf Order (Einzelorder)

        :param depot_id: Depot-ID
        :return: Response object
        """
        url = '{0}/brokerage/v3/orders/{1}'.format(self.api_url, order_id)
        params = {}

        response = self.session.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            raise OrderException(response.headers['x-http-response-info'])

    def set_validation_order(self, order):
        """
        7.1.5 Anlage Validation Orderanlage
        8.1.4 Anlage Validation Orderaufgabe
        -> von Georg

        :param order:  JSON-Objekt Order
        :return: challange id, None, body of validation order
        """
        url = '{0}/brokerage/v3/orders/validation'.format(self.api_url)
        response = self.session.post(url, json=order)
        # Bei Erfolg wird nur der http-status_code zurückgegeben, ansonsten ist der body leer
        if response.status_code == 201:
            response_json = json.loads(response.headers['x-once-authentication-info'])

            # print("json response header in set_validation_order:")
            # print(response_json)
            # print("json full response object")
            # print(response)

            # Gib challange id zurueck
            challangeType = response_json['typ']

            # Is it a P-TAN or M-TAN challenge (this would be bad because it should already
            # have activated the session-TAN)
            if challangeType == 'P_TAN' or challangeType == 'M_TAN':
                return response_json['id'], response_json['challenge'], None
            else:
                return response_json['id'], None, json.loads(response.text)
        else:
            raise OrderException(response.headers['x-http-response-info'])

    def set_order(self, order, challenge_id):
        """
        7.1.7 Anlage Orderanlage
        8.1.5 Anlage Orderanlage
        -> von Georg

        :param order:  JSON-Objekt Order
        :param challenge_id:  id der Challange aus der set_validation_order-Antwort
        :return: Order-Object als dictionary
        """
        url = '{0}/brokerage/v3/orders'.format(self.api_url)

        headers = {
            'x-once-authentication-info': json.dumps({
                "id": challenge_id
            })
        }

        response = self.session.post(url, headers=headers, json=order)

        if response.status_code == 201:

            # print("json full response in set_order:")
            # print(response.json())

            return response.json()

        else:
            raise OrderException(response.status_code)

    def set_change_validation(self, order_id, changed_order):
        """
        #TODO: das war um upstream falsch!
        7.1.9 Anlage Validation Orderänderung und Orderlöschung

        :param order_id: Order-ID
        :param changed_order: Altered order from get_order
        :return: [challenge_id, challenge] (if challenge not neccessary: None)
        """
        url = '{0}/brokerage/v3/orders/{1}/validation'.format(self.api_url, order_id)
        response = self.session.post(url, json=changed_order)
        if response.status_code == 201:
            response_json = json.loads(response.headers['x-once-authentication-info'])
            typ = response_json['typ']
            print("TAN-TYP: {}".format(typ))
            if typ == 'P_TAN' or typ == 'M_TAN':
                return response_json['id'], response_json['challenge']
            else:
                return response_json['id'], None
        else:
            raise OrderException(response.headers['x-http-response-info'])

    def set_change(self, order_id, changed_order, challenge_id, tan=None):
        """
        7.1.11 Änderung der Order

        :param order_id: Order-ID
        :param changed_order: same altered order as for set_change_validation
        :param challenge_id: first return value from set_change_validation
        :param tan: tan if neccessary
        :return: Response object
        """
        url = '{0}/brokerage/v3/orders/{1}'.format(self.api_url, order_id)
        headers = {
            'x-once-authentication-info': json.dumps({
                "id": challenge_id
            })
        }
        if tan is not None:
            headers['x-once-authentication'] = str(tan)

        response = self.session.patch(url, headers=headers, json=changed_order)
        if response.status_code == 200:
            return response.json()
        else:
            raise OrderException(response.headers['x-http-response-info'])

    def set_validation_quote(self, order):
        """
        8.1.1 Anlage Validation Quote
        Creates TAN challange
        -> von Georg

        :param order:  JSON-Objekt Order
        :return: challange id, None, body of validation order
        """
        url = '{0}/brokerage/v3/quoteticket'.format(self.api_url)
        response = self.session.post(url, json=order)
        # Bei Erfolg wird nur der http-status_code zurückgegeben, ansonsten ist der body leer
        if response.status_code == 201:
            response_json = json.loads(response.headers['x-once-authentication-info'])

            # print("json response header in set_validation_order:")
            # print(response_json)
            # print("json full response object")
            # print(response)

            # Gib challange id zurueck
            challangeType = response_json['typ']

            # Is it a P-TAN or M-TAN challenge (this would be bad because it should already
            # have activated the session-TAN)
            if challangeType == 'P_TAN' or challangeType == 'M_TAN':
                return response_json['id'], response_json['challenge']
            else:
            # We use the session TAN
                return response_json['id'], None, json.loads(response.text)
        else:
            # raise OrderException(response.headers['x-http-response-info'])
            raise OrderException(response.text)

    def set_validation_quote_tan(self, quote_ticket_id, challenge_id):
        """
        8.1.2  Aenderung Validierung Quote Request-Initialisierung mit TAN
        (=Aktivierung des Quote-Tickets mit der Session-TAN)
        Ist nur für Session-TAN implmementiert.

        :param quote_ticket_id: quoteTicketId, für die die TAN-Challenge übergeben wird
        :param challenge_id: TAN-Challenge aus der Validations-Schnittstelle
        :return: Response status code (=204) or throw an error if it is not 204
        """
        # url = '{0}/brokerage/v3/orders/quoteticket/{1}'.format(self.api_url, quote_ticket_id)
        url = '{0}/brokerage/v3/quoteticket/{1}'.format(self.api_url, quote_ticket_id)
        # TODO: Steht falsch in der Doku, die Url muss ohne .../orders/... sein.
        headers = {
            'x-once-authentication-info': json.dumps({
                "id": challenge_id
            })

        }

        #response = self.session.patch(url, headers=headers, json=changed_order)
        response = self.session.patch(url, headers=headers)
        if response.status_code == 204:
            return response.status_code
        else:
            raise OrderException(response.headers['x-http-response-info'])

    def set_quote_request(self, order, quoteTicketId):
        """
        8.1.3 Anlage Quote Request
        Bei diesem Aufruf wird der Quote-Request mit Referenz auf die quoteTicketId übergeben.
        -> von Georg

        :param order:  JSON-Objekt Order
        :param quoteTicketId: quoteTicketId
        :return: Ein- oder beidseitiger Quote des Handelsplatzes mit jeweiliger Quantity und Gültigkeit)
        """
        url = '{0}/brokerage/v3/quotes'.format(self.api_url)
        response = self.session.post(url, json=order)
        # (= Ein- oder beidseitiger Quote des Handelsplatzes mit jeweiliger Quantity und Gültigkeit)
        if response.status_code == 200:
            # response_json = json.loads(response.headers['x-once-authentication-info'])

            # print("json response header in set_validation_order:")
            # print(response_json)
            # print("json full response object")
            # print(response)

            return response.status_code, response.json()

        else:
            # Error
            return response.status_code, response.text

        # else:
            # raise OrderException(response.headers['x-http-response-info'])


class OrderException(Exception):
    def __init__(self, response_info):
        self.response_info = response_info
        super().__init__(self.response_info)
