# -*- coding: utf-8 -*-
"""
Created on Tue Jun 23 09:22:17 2020

@author: arogers
"""
from ast import Sub
from opcua import ua
import numpy as np
from threading import Thread
from time import sleep

class SubHandler():
        """
        Subscription Handler. To receive events from server for a subscription
        data_change and event methods are called directly from receiving thread.
        Do not do expensive, slow or network operation there. Create another 
        thread if you need to do such a thing
        """
        def __init__(self, tag):
            self.tag = tag
            pass

        def datachange_notification(self, node, val, data):
            if (self.tag.name != "ns=6;s=::AsGlobalPV:gOpcData_ToCalibApp.HeartbeatOut"):
                print(self.tag.name + " changed to " + str(val))
            t = Thread(target=self.updateTag, args=(val,))
            t.start()
            pass

        def event_notification(self, event):
            pass   

        def updateTag(self, val):
            self.tag.value = val
            pass


class BNRopcuaTag:
    def __init__(self, client, VarName):
       self.client = client
       self.name = VarName
       self.node=client.get_node(VarName)
       self.subscription = False
       self._value = None
       self._observers = []

    @property
    def value(self):
        if self.subscription:
            return self._value
        else:
            self._value = self.node.get_value()
            return self._value
       
    @value.setter
    def value(self, val):
        if self._value != val:
            self._value = val
            self.react()

    
    def setPlcValue(self, val):
        if self.subscription:
            print('Variable not Settable\n')
        else:
            vartype=self.node.get_data_type_as_variant_type()
            if isinstance(val,bool):
                self.node.set_value(ua.DataValue(ua.Variant(val,vartype)))
            elif isinstance(val,int):
                self.node.set_value(ua.DataValue(ua.Variant(int(val),vartype)))
            elif isinstance(val,float):
                self.node.set_value(ua.DataValue(ua.Variant(val,ua.VariantType.Float)))
            elif isinstance(val, list) and self.node.get_array_dimensions()[0] > 0:
                pixels = self.node.get_children()
                if len(val) < len(pixels):
                    for i in range(len(val)):
                        pixels[i].set_value(ua.DataValue(ua.Variant(int(val[i]),vartype)))
            else:
                print(self.name + " Value: " + str(val) + " Type: " + str(type(val)) + ' Invalid Data Type\n')
            self.value = val



    def _setAsUpdating(self):
        sleep(0.1)
        self.subscription = True
        self.VarHandler = SubHandler(self)
        self.VariableSub=self.client.create_subscription(200, self.VarHandler)
        self.SubHandle=self.VariableSub.subscribe_data_change(self.node)
                        
    def _removeUpdates(self):
        if self.subscription:
            self.VariableSub.unsubscribe(self.SubHandle)
            self.VariableSub.delete() 

    def react(self):
        """Run reactions"""
        [Thread(target=func).start() for func in self._observers]
 
    def attachReaction(self, observer):
        """If the observer is not in the list,
        append it into the list"""
        if observer not in self._observers:
            self._observers.append(observer)
 
    def detachReaction(self, observer):
        """Remove the observer from the observer list"""
        try:
            self._observers.remove(observer)
        except ValueError:
            pass
                    
    

                 
           
        
            
        