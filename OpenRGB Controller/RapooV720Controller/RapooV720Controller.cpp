/*---------------------------------------------------------*\
| RapooV720Controller.cpp |
|                                                           |
|   Rapoo V720 keyboard (patched firmware, direct mode)     |
|                                                           |
|   This file is part of the OpenRGB project                |
|   SPDX-License-Identifier: GPL-2.0-or-later               |
\*---------------------------------------------------------*/

#include <thread>
#include <cstdlib>
#include "RapooV720Controller.h"
#include "StringUtils.h"

/*---------------------------------------------------------*\
| The keyboard handles key presses in its main loop, which  |
| also receives these reports. Sending them unpaced makes   |
| it miss key presses, so limit the rate. With the v9       |
| firmware patch (docs/FIRMWARE-PATCHES.md) 1600 per second |
| was tested without missed keys; with older patch versions |
| use a lower value (about 400-800).                        |
\*---------------------------------------------------------*/
#define RAPOO_V720_DEFAULT_REPORTS_PER_SECOND   1600

/*---------------------------------------------------------*\
| The limit can be changed without rebuilding by setting    |
| the environment variable RAPOO_V720_MAX_RATE (50..2000)   |
\*---------------------------------------------------------*/
static int RapooV720MaxRate()
{
    static int rate = 0;

    if(rate == 0)
    {
        rate = RAPOO_V720_DEFAULT_REPORTS_PER_SECOND;

        const char* env = std::getenv("RAPOO_V720_MAX_RATE");

        if(env != nullptr)
        {
            int value = std::atoi(env);

            if(value >= 50 && value <= 2000)
            {
                rate = value;
            }
        }
    }

    return(rate);
}

RapooV720Controller::RapooV720Controller(hid_device* dev_handle, const char* path, std::string dev_name)
{
    dev         = dev_handle;
    location    = path;
    name        = dev_name;
    next_send   = std::chrono::steady_clock::now();
}

RapooV720Controller::~RapooV720Controller()
{
    hid_close(dev);
}

std::string RapooV720Controller::GetDeviceLocation()
{
    return("HID: " + location);
}

std::string RapooV720Controller::GetNameString()
{
    return(name);
}

std::string RapooV720Controller::GetSerialString()
{
    wchar_t serial_string[128];
    int ret = hid_get_serial_number_string(dev, serial_string, 128);

    if(ret != 0)
    {
        return("");
    }

    return(StringUtils::wstring_to_string(serial_string));
}

bool RapooV720Controller::SetKey(unsigned char key_index, unsigned char red, unsigned char green, unsigned char blue)
{
    unsigned char buf[6] = { 0x05, 0xE0, key_index, red, green, blue };

    /*-----------------------------------------------------*\
    | Pace the reports. This waits, so it must only be      |
    | called from the sender thread, never from OpenRGB's   |
    | update path                                           |
    \*-----------------------------------------------------*/
    std::chrono::steady_clock::time_point now = std::chrono::steady_clock::now();

    while(std::chrono::steady_clock::now() < next_send)
    {
        std::this_thread::yield();
    }

    if(now > next_send)
    {
        next_send = now;
    }

    next_send += std::chrono::microseconds(1000000 / RapooV720MaxRate());

    return(hid_send_feature_report(dev, buf, sizeof(buf)) > 0);
}
