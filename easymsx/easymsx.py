# easymsx.py

import blpapi
import logging
from enum import Enum
from easymsx.schemafielddefinition import SchemaFieldDefinition
from easymsx.teams import Teams
from easymsx.brokers import Brokers
from easymsx.orders import Orders
from easymsx.routes import Routes

# ADMIN
SLOW_CONSUMER_WARNING = blpapi.Name("SlowConsumerWarning")
SLOW_CONSUMER_WARNING_CLEARED = blpapi.Name("SlowConsumerWarningCleared")

# SESSION_STATUS
SESSION_STARTED = blpapi.Name("SessionStarted")
SESSION_TERMINATED = blpapi.Name("SessionTerminated")
SESSION_STARTUP_FAILURE = blpapi.Name("SessionStartupFailure")
SESSION_CONNECTION_UP = blpapi.Name("SessionConnectionUp")
SESSION_CONNECTION_DOWN = blpapi.Name("SessionConnectionDown")

# SERVICE_STATUS
SERVICE_OPENED = blpapi.Name("ServiceOpened")
SERVICE_OPEN_FAILURE = blpapi.Name("ServiceOpenFailure")

# SUBSCRIPTION_STATUS + SUBSCRIPTION_DATA
SUBSCRIPTION_FAILURE = blpapi.Name("SubscriptionFailure")
SUBSCRIPTION_STARTED = blpapi.Name("SubscriptionStarted")
SUBSCRIPTION_TERMINATED = blpapi.Name("SubscriptionTerminated")

logger = logging.getLogger(__name__)


class EasyMSX:

    # next correlation ID to be used
    next_cor_id = 1

    class Environment(Enum):
        PRODUCTION = 0
        BETA = 1

    def __init__(self, env=Environment.BETA, host="localhost", port=8194, lvl=logging.CRITICAL):

        self.set_log_level(lvl)

        self.env = env
        self.host = host
        self.port = port

        self.external_wait = None
        self.external_message = None

        self.notification_handlers = []
        self.request_message_handlers = {}
        self.subscription_message_handlers = {}
        self.order_fields = []
        self.route_fields = []
        self.emsx_service_name = ""
        self.teams = None

        self.team = None

        self.session_options = blpapi.SessionOptions()
        self.session = blpapi.Session(options=self.session_options, eventHandler=self.process_event)
        self.emsx_service = None
        self.order_route_fields = None
        self.brokers = None

        self.initialize()

        self.orders = Orders(self)
        self.routes = Routes(self)

    @staticmethod
    def set_log_level(lvl):
        logging.basicConfig(level=lvl)

    def initialize(self):

        self.initialize_session()
        self.initialize_service()
        self.initialize_field_data()
        self.initialize_teams()
        self.initialize_broker_data()

        # wait until all request responses have been received
        while len(self.request_message_handlers) > 0:
            pass

    def initialize_session(self):
        if self.env == self.Environment.BETA:
            self.emsx_service_name = "//blp/emapisvc_beta"
        elif self.env == self.Environment.PRODUCTION:
            self.emsx_service_name = "//blp/emapisvc"

        self.session_options.setServerHost(self.host)
        self.session_options.setServerPort(self.port)

        if not self.session.start():
            raise ValueError("Failed to start session.")

    def initialize_service(self):
        if not self.session.openService(self.emsx_service_name):
            self.session.stop()
            raise ValueError("Unable to open EMSX service")

        self.emsx_service = self.session.getService(self.emsx_service_name)

    def initialize_field_data(self):

        logger.info("Initializing field data...")

        self.order_route_fields = self.emsx_service.getEventDefinition("OrderRouteFields")
        type_def = self.order_route_fields.typeDefinition()

        logger.info("Total number of fields: %d" % (type_def.numElementDefinitions()))

        for i in range(0, type_def.numElementDefinitions()):

            e = type_def.getElementDefinition(i)

            name = str(e.name())

            # Workaround for schema field naming
            if name == "EMSX_ORD_REF_ID":
                name = "EMSX_ORDER_REF_ID"
            # End of Workaround

            f = SchemaFieldDefinition(name)

            f.status = e.status()
            f.type = e.typeDefinition().description()
            f.min = e.minValues()
            f.max = e.maxValues()
            f.description = e.description()

            if f.is_order_field():
                self.order_fields.append(f)
                logger.info("Added order field: " + f.name)
            if f.is_route_field():
                self.route_fields.append(f)
                logger.info("Added route field: " + f.name)

            logger.info("Adding field: " + f.name + "\tStatus: " + str(f.status) + "\tType: " + f.type)

    def initialize_teams(self):
        self.teams = Teams(self)

    def initialize_broker_data(self):
        self.brokers = Brokers(self)

    def start(self):
        self.initialize_orders()
        self.initialize_routes()

    def stop(self):
        self.session.stop()

    def initialize_orders(self):
        self.orders.subscribe()

    def initialize_routes(self):
        self.routes.subscribe()

    def set_team(self, selected_team):
        self.team = selected_team

    def submit_request(self, req, message_handler):
        try:
            cid = self.session.sendRequest(request=req)
            self.request_message_handlers[cid.value()] = message_handler
            logger.info("Request submitted (" + str(cid) + "): \n" + str(req))

        except Exception as err:
            logger.error("EasyMSX >>  Error submitting request: " + str(err))

    def subscribe(self, topic, message_handler):
        try:
            self.next_cor_id += 1
            cid = blpapi.CorrelationId(self.next_cor_id)
            subscriptions = blpapi.SubscriptionList()
            subscriptions.add(topic=topic, correlationId=cid)
            self.session.subscribe(subscriptions)
            self.subscription_message_handlers[cid.value()] = message_handler
            logger.info("Request submitted (" + str(cid) + "): \n" + str(topic))

        except Exception as err:
            logger.error("EasyMSX >>  Error subscribing to topic: " + str(err))

    def process_event(self, event, session):

        logger.info("Processing Event (" + str(event.eventType()) + ") on session " + str(session))

        if event.eventType() == blpapi.Event.ADMIN:
            self.process_admin_event(event)

        elif event.eventType() == blpapi.Event.SESSION_STATUS:
            self.process_session_status_event(event)

        elif event.eventType() == blpapi.Event.SERVICE_STATUS:
            self.process_service_status_event(event)

        elif event.eventType() == blpapi.Event.SUBSCRIPTION_DATA:
            self.process_subscription_data_event(event)

        elif event.eventType() == blpapi.Event.SUBSCRIPTION_STATUS:
            self.process_subscription_status_event(event)

        elif event.eventType() == blpapi.Event.RESPONSE:
            self.process_response_event(event)

        else:
            self.process_misc_events(event)

        return False

    @staticmethod
    def process_admin_event(event):

        logger.info("Processing ADMIN event...")

        for msg in event:
            if msg.messageType() == SLOW_CONSUMER_WARNING:
                logger.warning("Slow Consumer Warning")
            elif msg.messageType() == SLOW_CONSUMER_WARNING_CLEARED:
                logger.warning("Slow Consumer Warning cleared")

    @staticmethod
    def process_session_status_event(event):

        logger.info("Processing SESSION_STATUS event...")

        for msg in event:
            if msg.messageType() == SESSION_STARTED:
                logger.info("Session Started")
            elif msg.messageType() == SESSION_STARTUP_FAILURE:
                logger.warning("Session Startup Failure")
            elif msg.messageType() == SESSION_TERMINATED:
                logger.info("Session Terminated")
            elif msg.messageType() == SESSION_CONNECTION_UP:
                logger.info("Session Connection Up")
            elif msg.messageType() == SESSION_CONNECTION_DOWN:
                logger.info("Session Connection Down")

    @staticmethod
    def process_service_status_event(event):

        logger.info("Processing SERVICE_STATUS event...")

        for msg in event:
            if msg.messageType() == SERVICE_OPENED:
                logger.info("Service Opened")
            elif msg.messageType() == SERVICE_OPEN_FAILURE:
                logger.warning("Service Open Failure")

    def process_subscription_data_event(self, event):

        logger.info("Processing SUBSCRIPTION_DATA event...")

        for msg in event:
            cid = msg.correlationIds()[0].value()
            if cid in self.subscription_message_handlers:
                self.subscription_message_handlers[cid](msg)
            else:
                logger.error("Unrecognised correlation ID in subscription data event. No event handler can be found for cid: " + str(cid))

    def process_subscription_status_event(self, event):

        logger.info("Processing SUBSCRIPTION_STATUS event...")

        for msg in event:
            cid = msg.correlationIds()[0].value()
            if cid in self.subscription_message_handlers:
                self.subscription_message_handlers[cid](msg)
            else:
                logger.error("Unrecognised correlation ID in subscription status event. No event handler can be found for cid: " + str(cid))

    def process_response_event(self, event):

        logger.info("Processing RESPONSE event...")

        for msg in event:
            cid = msg.correlationIds()[0].value()
            logger.debug("Received cid: " + str(cid))
            if cid in self.request_message_handlers:
                handler = self.request_message_handlers[cid]
                handler(msg)
                del self.request_message_handlers[cid]
            else:
                logger.error("Unrecognised correlation ID in response event. No event handler can be found for cID: " + str(cid))

    @staticmethod
    def process_misc_events(event):

        logger.info("Processing unknown event...")

        for msg in event:
            logger.info("Misc Event: " + msg)

    def add_notification_handler(self, handler):
        self.notification_handlers.append(handler)

    def notify(self, notification):
        for h in self.notification_handlers:
            if not notification.consumed:
                h(notification)

    def send_request(self, req, message_handler=None):
        try:
            if message_handler is None:
                self.external_wait = True
                cid = self.session.sendRequest(request=req)
                self.request_message_handlers[cid.value()] = self.process_external_response
                while self.external_wait:
                    pass
                return self.external_message

            else:
                cid = self.session.sendRequest(request=req)
                self.request_message_handlers[cid.value()] = message_handler
                logger.debug("Request submitted (" + str(cid) + "): \n" + str(req))

        except Exception as err:
            logger.error("EasyMSX >>  Error sending request: " + str(err))

    def process_external_response(self, message):

        self.external_message = message
        self.external_wait = False

    def create_request(self, operation):

        return self.emsx_service.createRequest(operation)


__copyright__ = """
Copyright 2017. Bloomberg Finance L.P.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to
deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
sell copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:  The above
copyright notice and this permission notice shall be included in all copies
or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NON-INFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
IN THE SOFTWARE.
"""
