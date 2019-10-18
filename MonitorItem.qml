// Copyright (c) 2018 Ultimaker B.V.
// Cura is released under the terms of the LGPLv3 or higher.

import QtQuick 2.2
import QtQuick.Controls 1.1
import QtQuick.Controls.Styles 1.1
import QtQuick.Layouts 1.1

import UM 1.2 as UM
import Cura 1.0 as Cura
Component
{
    Item
    {
        UM.I18nCatalog
        {
            id: catalog
            name: "cura"
        }

        property var connectedDevice: Cura.MachineManager.printerOutputDevices.length >= 1 ? Cura.MachineManager.printerOutputDevices[0] : null

        Rectangle
        {
            color: UM.Theme.getColor("main_background")

            anchors.right: parent.right
            width: parent.width * 0.3
            anchors.top: parent.top
            anchors.bottom: parent.bottom


            Button // The connect/disconnect button.
            {
                id: connectButton
                height: UM.Theme.getSize("setting_control").height
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: UM.Theme.getSize("default_margin").width
                style: ButtonStyle {
                    background: Rectangle
                    {
                        border.width: UM.Theme.getSize("default_lining").width
                        implicitWidth: actualLabel.contentWidth + (UM.Theme.getSize("default_margin").width * 2)
                        border.color:
                        {
                            if(!control.enabled)
                            {
                                return UM.Theme.getColor("action_button_disabled_border");
                            }
                            else if(control.pressed)
                            {
                                return UM.Theme.getColor("action_button_active_border");
                            }
                            else if(control.hovered)
                            {
                                return UM.Theme.getColor("action_button_hovered_border");
                            }
                            else
                            {
                                return UM.Theme.getColor("action_button_border");
                            }
                        }
                        color:
                        {
                            if(!control.enabled)
                            {
                                return UM.Theme.getColor("action_button_disabled");
                            }
                            else if(control.pressed)
                            {
                                return UM.Theme.getColor("action_button_active");
                            }
                            else if(control.hovered)
                            {
                                return UM.Theme.getColor("action_button_hovered");
                            }
                            else
                            {
                                return UM.Theme.getColor("action_button");
                            }
                        }
                        Behavior on color
                        {
                            ColorAnimation
                            {
                                duration: 50
                            }
                        }

                        Label
                        {
                            id: actualLabel
                            anchors.centerIn: parent
                            color:
                            {
                                if(!control.enabled)
                                {
                                    return UM.Theme.getColor("action_button_disabled_text");
                                }
                                else if(control.pressed)
                                {
                                    return UM.Theme.getColor("action_button_active_text");
                                }
                                else if(control.hovered)
                                {
                                    return UM.Theme.getColor("action_button_hovered_text");
                                }
                                else
                                {
                                    return UM.Theme.getColor("action_button_text");
                                }
                            }
                            font: UM.Theme.getFont("medium")
                            text:
                            {
                                if(connectedDevice == null)
                                {
                                    return ""
                                }
                                if(!connectedDevice.acceptsCommands)
                                {
                                    return catalog.i18nc("@button", "Connect")
                                } else
                                {
                                    return catalog.i18nc("@button", "Disconnect")
                                }
                            }
                        }
                    }
                }

                onClicked:
                {
                    if (!connectedDevice.acceptsCommands)
                    {
                        enabled = false;
                        connectedDevice.goOnline();
                    }
                    else
                    {
                        enabled = false;
                        connectedDevice.goOffline();
                    }
                }
            }

            Connections
            {
                target: connectedDevice
                onAcceptsCommandsChanged:
                {
                    connectButton.enabled = true
                }
            }


            Cura.PrintMonitor
            {
                anchors.fill: parent
            }

            Rectangle
            {
                id: footerSeparator
                width: parent.width
                height: UM.Theme.getSize("wide_lining").height
                color: UM.Theme.getColor("wide_lining")
                anchors.bottom: monitorButton.top
                anchors.bottomMargin: UM.Theme.getSize("thick_margin").height
            }

            // MonitorButton is actually the bottom footer panel.
            Cura.MonitorButton
            {
                id: monitorButton
                anchors.bottom: parent.bottom
                anchors.left: parent.left
                anchors.right: parent.right
            }
        }
    }
}