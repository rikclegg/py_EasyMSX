# route.py

from .fields import Fields
from .notification import Notification

class Route:
    
    def __init__(self, parent):
        self.parent = parent
        self.sequence = 0
        self.route_id = 0
        self.notification_handlers = []
        self.fields=Fields(self)
        
    def field(self,field_name):
        return self.fields.field(field_name)

    def add_notification_handler(self,handler):
        self.notification_handlers.append(handler)

    def notify(self, notification):
        for h in self.notification_handlers:
            if not notification.consumed:
                h(notification)
        if not notification.consumed: 
            self.parent.notify(notification)

    def get_notification_category(self):
        return Notification.NotificationCategory.ROUTE
    

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
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
IN THE SOFTWARE.
"""
