/*---------------------------------------------------------*\
| RGBController_RapooV720.h |
|                                                           |
|   Rapoo V720 keyboard (patched firmware, direct mode)     |
|                                                           |
|   This file is part of the OpenRGB project                |
|   SPDX-License-Identifier: GPL-2.0-or-later               |
\*---------------------------------------------------------*/

#pragma once

#include <atomic>
#include <condition_variable>
#include <mutex>
#include <thread>
#include <vector>
#include "RGBController.h"
#include "RapooV720Controller.h"

class RGBController_RapooV720 : public RGBController
{
public:
    RGBController_RapooV720(RapooV720Controller* controller_ptr);
    ~RGBController_RapooV720();

    void            SetupZones();

    void            DeviceUpdateLEDs();
    void            DeviceUpdateZoneLEDs(int zone);
    void            DeviceUpdateSingleLED(int led);

    void            DeviceUpdateMode();

private:
    RapooV720Controller*    controller;
    std::vector<RGBColor>   sent_colors;
    std::vector<bool>       sent_valid;
    std::vector<unsigned int> age;

    /*-----------------------------------------------------*\
    | A sender thread keeps sending until every key matches |
    | the latest colours OpenRGB asked for, so OpenRGB's    |
    | update call never waits and the last colour always    |
    | wins                                                  |
    \*-----------------------------------------------------*/
    void                    SenderLoop();
    std::thread             sender;
    std::mutex              sender_mutex;
    std::condition_variable sender_cv;
    std::vector<RGBColor>   target;
    std::atomic<unsigned long> generation;
    bool                    has_work;
    bool                    stop_sender;
};
