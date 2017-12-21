'''
Created on 21 Dec 2017

@author: RCLEGG2@BLOOMBERG.NET
'''

import unittest
import time
from easymsx import easymsx 

class TestEasyMSX(unittest.TestCase):

    def process_notification(self,notification):

        if notification.category == easymsx.EasyMSX.NotificationCategory.ORDER:
            if notification.type == easymsx.EasyMSX.NotificationType.NEW or notification.type == easymsx.EasyMSX.NotificationType.INITIALPAINT: 
                print("EasyMSX Notification ORDER -> NEW/INIT_PAINT")
                #self.parse_order(notification.source)
        
        if notification.category == easymsx.EasyMSX.NotificationCategory.ROUTE:
            if notification.type == easymsx.EasyMSX.NotificationType.NEW or notification.type == easymsx.EasyMSX.NotificationType.INITIALPAINT: 
                print("EasyMSX Notification ROUTE -> NEW/INIT_PAINT")
                #self.parse_route(notification.source)

    def test_start_easymsx_does_not_fail(self):

        raised = False
        
        try:
            emsx = easymsx.EasyMSX()
            emsx.orders.add_notification_handler(self.process_notification)
            emsx.routes.add_notification_handler(self.process_notification)

            emsx.start()
            
        except BaseException as e:
            print("Error: " + str(e))
            raised=True
        
        self.assertFalse(raised)
