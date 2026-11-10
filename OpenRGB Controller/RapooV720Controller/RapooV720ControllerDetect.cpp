/*---------------------------------------------------------*\
| RapooV720ControllerDetect.cpp |
|                                                           |
|   Rapoo V720 keyboard (patched firmware, direct mode)     |
|                                                           |
|   This file is part of the OpenRGB project                |
|   SPDX-License-Identifier: GPL-2.0-or-later               |
\*---------------------------------------------------------*/

#include "DetectionManager.h"
#include "RapooV720Controller.h"
#include "RGBController_RapooV720.h"

#define RAPOO_VID           0x24AE
#define RAPOO_V720_PID      0x4018

/*---------------------------------------------------------*\
| The keyboard exposes several HID collections. Only one    |
| accepts the 6-byte report 5, so try it and keep only the  |
| collection that does.                                     |
\*---------------------------------------------------------*/
DetectedControllers DetectRapooV720(hid_device_info* info, const std::string& name)
{
    DetectedControllers detected_controllers;
    hid_device*         dev;

    dev = hid_open_path(info->path);

    if(dev)
    {
        unsigned char sync[6] = { 0x05, 0x83, 0x00, 0x00, 0x00, 0x00 };

        if(hid_send_feature_report(dev, sync, sizeof(sync)) > 0)
        {
            RapooV720Controller*     controller     = new RapooV720Controller(dev, info->path, name);
            RGBController_RapooV720* rgb_controller = new RGBController_RapooV720(controller);

            detected_controllers.push_back(rgb_controller);
        }
        else
        {
            hid_close(dev);
        }
    }

    return(detected_controllers);
}

REGISTER_HID_DETECTOR_IPU("Rapoo V720", DetectRapooV720, RAPOO_VID, RAPOO_V720_PID, 1, 0xFF00, 1);
