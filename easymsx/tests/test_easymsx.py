'''
Created on 21 Dec 2017

@author: RCLEGG2@BLOOMBERG.NET
'''

import unittest
import time
from easymsx import easymsx 

class TestEasyMSX(unittest.TestCase):

    def test_instantiate_easymsx_returns_teams(self):

        raised = False
        
        try:
            emsx = easymsx.EasyMSX()
            
        except BaseException as e:
            print("Error: " + str(e))
            raised=True
        
        self.assertFalse(raised)

