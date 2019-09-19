// Copyright (c) 2019 Aldo Hoeben / fieldOfView
// SerialConnection is released under the terms of the GPLv3 or higher.

import UM 1.2 as UM
import Cura 1.0 as Cura

import QtQuick 2.2
import QtQuick.Controls 1.1
import QtQuick.Layouts 1.1
import QtQuick.Window 2.1

Cura.MachineAction
{
    id: base
    anchors.fill: parent;
    property var selectedInstance: null
    Column
    {
        anchors.fill: parent;
        id: discoverOctoPrintAction

        spacing: UM.Theme.getSize("default_margin").height

        SystemPalette { id: palette }
        UM.I18nCatalog { id: catalog; name:"cura" }
        Label
        {
            id: pageTitle
            width: parent.width
            text: catalog.i18nc("@title", "Connect via USB")
            wrapMode: Text.WordWrap
            font.pointSize: 18
        }

        Label
        {
            id: pageDescription
            width: parent.width
            wrapMode: Text.WordWrap
            text: catalog.i18nc("@label", "Select the port and communication speed to use to connect with this printer.")
        }

        GridLayout
        {
            width: parent.width
            columns: 3
            columnSpacing: UM.Theme.getSize("default_margin").width
            rowSpacing: UM.Theme.getSize("default_lining").height

            Label
            {
                text: catalog.i18nc("@label", "Serial Port:")
            }
            ComboBox
            {
                id: connectionPort

                property bool populatingModel: false
                model: ListModel
                {
                    id: connectionPortModel

                    Component.onCompleted: populateModel()

                    function populateModel()
                    {
                        connectionPort.populatingModel = true;
                        clear();

                        append({
                            key: "NONE",
                            text: catalog.i18nc("@label", "Don't connect"),
                            available: false
                        });
                        var current_index = 0;

                        var port_list = manager.portList;
                        for(var index in port_list)
                        {
                            append({
                                key: port_list[index],
                                text: port_list[index],
                                available: true
                            });
                            if(port_list[index] == manager.serialPort)
                            {
                                current_index = index + 1;
                            }
                        }

                        if(current_index == 0 && manager.serialPort != "NONE" && manager.serialPort != "")
                        {
                            append({
                                key: manager.serialPort,
                                text: catalog.i18nc("@label", "%1 (not available)").arg(manager.serialPort),
                                available: false
                            });
                            current_index = count - 1;
                        }

                        connectionPort.currentIndex = current_index;
                        connectionPort.populatingModel = false;
                    }
                }

                onActivated:
                {
                    if(!populatingModel && model.get(index))
                    {
                        manager.setSerialPort(model.get(index).key);
                    }
                }

                Connections
                {
                    target: manager
                    onSerialPortsChanged: connectionPortModel.populateModel()
                }

            }
            Label { text: "" }
            Label
            {
                text: catalog.i18nc("@label", "Connection Speed:")
            }
            ComboBox
            {
                id: connectionRate
                model:
                {
                    var rates = [];
                    for(var index in manager.allBaudRates)
                    {
                        rates.push({key: manager.allBaudRates[index], text: manager.allBaudRates[index].toString()});
                    }
                    return rates;
                }
                enabled: connectionPortModel.get(connectionPort.currentIndex).key != "NONE"
                currentIndex:
                {
                    for(var index in model)
                    {
                        if(model[index].key == manager.baudRate)
                        {
                            return index;
                        }
                    }
                    return 0; // default to first in list
                }
                onActivated: manager.setBaudRate(model[index].key)
            }

            Button
            {
                id: detectButton
                text: catalog.i18nc("@action:button", "Detect")
                enabled: connectionPortModel.count > 1 && connectionPortModel.get(connectionPort.currentIndex).available
            }
        }

        CheckBox
        {
            id: autoConnect
            text: catalog.i18nc("@label", "Automatically connect this printer on startup.")
            checked: manager.autoConnect
            visible: connectionPortModel.get(connectionPort.currentIndex).key != "NONE"
            onClicked: manager.setAutoConnect(checked)
        }

        Label
        {
            width: parent.width
            wrapMode: Text.WordWrap
            visible: autoConnect.visible && autoConnect.checked
            text: catalog.i18nc("@label", "Note: connecting to a printer will interrupt ongoing prints on the printer.")
        }

        Button
        {
            id: testCommunication
            text: catalog.i18nc("@action:button", "Test Communication")
            visible: connectionPortModel.get(connectionPort.currentIndex).key != "NONE"
            enabled: connectionPortModel.get(connectionPort.currentIndex).available
            onClicked:
            {
                testOutput.visible = true
            }
        }

        TextArea
        {
            id: testOutput
            visible: false
            text: "Sent: M105\nReceived: T:19.6 /0.0 B:16.8 /0.0 B@:0 @:0\n\nSent: M115\nReceived: FIRMWARE_NAME:Marlin Ultimaker2; Sprinter/grbl mashup for gen6 FIRMWARE_URL:http://github.com/Ultimaker PROTOCOL_VERSION:1.0 MACHINE_TYPE:Ultimaker EXTRUDER_COUNT:1"
            width: parent.width
            height: base.height - testOutput.y
        }
    }
}