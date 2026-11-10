/*---------------------------------------------------------*\
| RapooV720Controller.h                                     |
|                                                           |
|   Rapoo V720 keyboard (patched firmware, direct mode)     |
|                                                           |
|   This file is part of the OpenRGB project                |
|   SPDX-License-Identifier: GPL-2.0-or-later               |
\*---------------------------------------------------------*/

#pragma once

#include <string>
#include <chrono>
#include <hidapi.h>
#include "RGBController.h"

/*---------------------------------------------------------*\
| Patched-firmware command (6-byte feature report):         |
|   05 E0 <key index> <R> <G> <B>                           |
| The key index is row * 22 + column of the keyboard matrix |
\*---------------------------------------------------------*/
class RapooV720Controller
{
public:
    RapooV720Controller(hid_device* dev_handle, const char* path, std::string dev_name);
    ~RapooV720Controller();

    std::string     GetDeviceLocation();
    std::string     GetNameString();
    std::string     GetSerialString();

    /*-----------------------------------------------------*\
    | Send one key colour, paced to the report rate limit.  |
    | Waits for its turn: call it from one worker thread    |
    \*-----------------------------------------------------*/
    bool            SetKey(unsigned char key_index, unsigned char red, unsigned char green, unsigned char blue);

private:
    hid_device*     dev;
    std::string     location;
    std::string     name;
    std::chrono::steady_clock::time_point next_send;
};
