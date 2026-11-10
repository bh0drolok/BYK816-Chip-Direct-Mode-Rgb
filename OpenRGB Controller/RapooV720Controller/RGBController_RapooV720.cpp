/*---------------------------------------------------------*\
| RGBController_RapooV720.cpp |
|                                                           |
|   Rapoo V720 keyboard (patched firmware, direct mode)     |
|                                                           |
|   This file is part of the OpenRGB project                |
|   SPDX-License-Identifier: GPL-2.0-or-later               |
\*---------------------------------------------------------*/

#include "RGBController_RapooV720.h"
#include <algorithm>
#include <cstdlib>
#include <cstring>
#include "RGBControllerKeyNames.h"
#include "KeyboardLayoutManager.h"

/*---------------------------------------------------------*\
| Hardware key index of every key (name -> index)           |
\*---------------------------------------------------------*/
#define RAPOO_V720_NO_KEY   0xFFFFFFFF

/*---------------------------------------------------------*\
| Key index (row * 22 + column in the keyboard's own        |
| addressing) and name of each key                          |
\*---------------------------------------------------------*/
struct rapoo_v720_led
{
    unsigned char   key_index;
    const char*     name;
};

static const rapoo_v720_led led_list[104] =
{
    { 0  , KEY_EN_ESCAPE },
    { 2  , KEY_EN_F1 },
    { 3  , KEY_EN_F2 },
    { 4  , KEY_EN_F3 },
    { 5  , KEY_EN_F4 },
    { 7  , KEY_EN_F5 },
    { 8  , KEY_EN_F6 },
    { 9  , KEY_EN_F7 },
    { 10 , KEY_EN_F8 },
    { 11 , KEY_EN_F9 },
    { 12 , KEY_EN_F10 },
    { 13 , KEY_EN_F11 },
    { 14 , KEY_EN_F12 },
    { 15 , KEY_EN_PRINT_SCREEN },
    { 16 , KEY_EN_SCROLL_LOCK },
    { 17 , KEY_EN_PAUSE_BREAK },
    { 22 , KEY_EN_BACK_TICK },
    { 23 , KEY_EN_1 },
    { 24 , KEY_EN_2 },
    { 25 , KEY_EN_3 },
    { 26 , KEY_EN_4 },
    { 27 , KEY_EN_5 },
    { 28 , KEY_EN_6 },
    { 29 , KEY_EN_7 },
    { 30 , KEY_EN_8 },
    { 31 , KEY_EN_9 },
    { 32 , KEY_EN_0 },
    { 33 , KEY_EN_MINUS },
    { 34 , KEY_EN_EQUALS },
    { 36 , KEY_EN_BACKSPACE },
    { 37 , KEY_EN_INSERT },
    { 38 , KEY_EN_HOME },
    { 39 , KEY_EN_PAGE_UP },
    { 40 , KEY_EN_NUMPAD_LOCK },
    { 41 , KEY_EN_NUMPAD_DIVIDE },
    { 42 , KEY_EN_NUMPAD_TIMES },
    { 43 , KEY_EN_NUMPAD_MINUS },
    { 44 , KEY_EN_TAB },
    { 45 , KEY_EN_Q },
    { 46 , KEY_EN_W },
    { 47 , KEY_EN_E },
    { 48 , KEY_EN_R },
    { 49 , KEY_EN_T },
    { 50 , KEY_EN_Y },
    { 51 , KEY_EN_U },
    { 52 , KEY_EN_I },
    { 53 , KEY_EN_O },
    { 54 , KEY_EN_P },
    { 55 , KEY_EN_LEFT_BRACKET },
    { 56 , KEY_EN_RIGHT_BRACKET },
    { 57 , KEY_EN_ANSI_BACK_SLASH },
    { 59 , KEY_EN_DELETE },
    { 60 , KEY_EN_END },
    { 61 , KEY_EN_PAGE_DOWN },
    { 62 , KEY_EN_NUMPAD_7 },
    { 63 , KEY_EN_NUMPAD_8 },
    { 64 , KEY_EN_NUMPAD_9 },
    { 65 , KEY_EN_NUMPAD_PLUS },
    { 66 , KEY_EN_CAPS_LOCK },
    { 67 , KEY_EN_A },
    { 68 , KEY_EN_S },
    { 69 , KEY_EN_D },
    { 70 , KEY_EN_F },
    { 71 , KEY_EN_G },
    { 72 , KEY_EN_H },
    { 73 , KEY_EN_J },
    { 74 , KEY_EN_K },
    { 75 , KEY_EN_L },
    { 76 , KEY_EN_SEMICOLON },
    { 77 , KEY_EN_QUOTE },
    { 79 , KEY_EN_ANSI_ENTER },
    { 84 , KEY_EN_NUMPAD_4 },
    { 85 , KEY_EN_NUMPAD_5 },
    { 86 , KEY_EN_NUMPAD_6 },
    { 88 , KEY_EN_LEFT_SHIFT },
    { 90 , KEY_EN_Z },
    { 91 , KEY_EN_X },
    { 92 , KEY_EN_C },
    { 93 , KEY_EN_V },
    { 94 , KEY_EN_B },
    { 95 , KEY_EN_N },
    { 96 , KEY_EN_M },
    { 97 , KEY_EN_COMMA },
    { 98 , KEY_EN_PERIOD },
    { 99 , KEY_EN_FORWARD_SLASH },
    { 102, KEY_EN_RIGHT_SHIFT },
    { 104, KEY_EN_UP_ARROW },
    { 106, KEY_EN_NUMPAD_1 },
    { 107, KEY_EN_NUMPAD_2 },
    { 108, KEY_EN_NUMPAD_3 },
    { 109, KEY_EN_NUMPAD_ENTER },
    { 110, KEY_EN_LEFT_CONTROL },
    { 111, KEY_EN_LEFT_WINDOWS },
    { 112, KEY_EN_LEFT_ALT },
    { 115, KEY_EN_SPACE },
    { 118, KEY_EN_RIGHT_ALT },
    { 119, KEY_EN_RIGHT_WINDOWS },
    { 120, KEY_EN_MENU },
    { 122, KEY_EN_RIGHT_CONTROL },
    { 125, KEY_EN_LEFT_ARROW },
    { 126, KEY_EN_DOWN_ARROW },
    { 127, KEY_EN_RIGHT_ARROW },
    { 128, KEY_EN_NUMPAD_0 },
    { 130, KEY_EN_NUMPAD_PERIOD },
};

/**------------------------------------------------------------------*\
    @name Rapoo V720
    @category Keyboard
    @type USB
    @save :no:
    @direct :white_check_mark:
    @effects :no:
    @detectors DetectRapooV720
    @comment Requires the patched firmware (direct mode, RAM only).
\*-------------------------------------------------------------------*/

RGBController_RapooV720::RGBController_RapooV720(RapooV720Controller* controller_ptr)
{
    controller                  = controller_ptr;
    generation                  = 0;
    has_work                    = false;
    stop_sender                 = false;

    name                        = controller->GetNameString();
    vendor                      = "Rapoo";
    type                        = DEVICE_TYPE_KEYBOARD;
    description                 = "Rapoo V720 Keyboard (patched firmware)";
    location                    = controller->GetDeviceLocation();
    serial                      = controller->GetSerialString();

    mode Direct;
    Direct.name                 = "Direct";
    Direct.value                = 0;
    Direct.flags                = MODE_FLAG_HAS_PER_LED_COLOR;
    Direct.color_mode           = MODE_COLORS_PER_LED;
    modes.push_back(Direct);

    SetupZones();
}

RGBController_RapooV720::~RGBController_RapooV720()
{
    {
        std::lock_guard<std::mutex> lock(sender_mutex);
        stop_sender = true;
    }
    sender_cv.notify_all();

    if(sender.joinable())
    {
        sender.join();
    }

    Shutdown();

    delete controller;
}

static unsigned int RapooV720KeyIndex(const std::string& key_name)
{
    /*-----------------------------------------------------*\
    | The standard ANSI layout calls the key right of the   |
    | menu area "Right Fn"; this keyboard has a Windows key |
    | at that position (hardware index 119)                 |
    \*-----------------------------------------------------*/
    std::string lookup = key_name;

    if(lookup == KEY_EN_RIGHT_FUNCTION)
    {
        lookup = KEY_EN_RIGHT_WINDOWS;
    }

    for(unsigned int i = 0; i < 104; i++)
    {
        if(lookup == led_list[i].name)
        {
            return(led_list[i].key_index);
        }
    }

    return(RAPOO_V720_NO_KEY);
}

void RGBController_RapooV720::SetupZones()
{
    /*---------------------------------------------------------*\
    | Use OpenRGB's standard ANSI full-size layout so that the  |
    | key positions and sizes match a real keyboard             |
    \*---------------------------------------------------------*/
    KeyboardLayoutManager new_kb(KEYBOARD_LAYOUT_ANSI_QWERTY, KEYBOARD_SIZE_FULL);

    zone new_zone;
    new_zone.name               = "Keyboard";
    new_zone.type               = ZONE_TYPE_MATRIX;
    new_zone.leds_count         = new_kb.GetKeyCount();
    new_zone.leds_min           = new_zone.leds_count;
    new_zone.leds_max           = new_zone.leds_count;
    new_zone.matrix_map         = new_kb.GetKeyMap(KEYBOARD_MAP_FILL_TYPE_COUNT);
    zones.push_back(new_zone);

    for(unsigned int led_idx = 0; led_idx < new_zone.leds_count; led_idx++)
    {
        led new_led;
        new_led.name            = new_kb.GetKeyNameAt(led_idx);
        new_led.value           = RapooV720KeyIndex(new_led.name);
        leds.push_back(new_led);
    }

    SetupColors();

    sent_colors.assign(leds.size(), 0);
    sent_valid.assign(leds.size(), false);
    age.assign(leds.size(), 0);
    target.assign(leds.size(), 0);

    if(!sender.joinable())
    {
        sender = std::thread(&RGBController_RapooV720::SenderLoop, this);
    }
}

void RGBController_RapooV720::DeviceUpdateLEDs()
{
    /*-----------------------------------------------------*\
    | Only record the wanted colours (rounded to steps of 4)|
    | and wake the sender thread. Never waits.              |
    \*-----------------------------------------------------*/
    {
        std::lock_guard<std::mutex> lock(sender_mutex);

        for(std::size_t led_idx = 0; led_idx < leds.size() && led_idx < target.size(); led_idx++)
        {
            /*---------------------------------------------*\
            | ToRGBColor is a macro without parentheses     |
            | around its arguments, so compute the rounded  |
            | channels in variables first                   |
            \*---------------------------------------------*/
            unsigned char red       = (unsigned char)(RGBGetRValue(colors[led_idx]) & 0xFC);
            unsigned char green     = (unsigned char)(RGBGetGValue(colors[led_idx]) & 0xFC);
            unsigned char blue      = (unsigned char)(RGBGetBValue(colors[led_idx]) & 0xFC);

            target[led_idx]         = ToRGBColor(red, green, blue);
        }

        has_work = true;
        generation++;
    }

    sender_cv.notify_one();
}

void RGBController_RapooV720::SenderLoop()
{
    struct Pending
    {
        unsigned int    score;
        std::size_t     led;
    };

    std::vector<RGBColor> wanted;

    while(true)
    {
        unsigned long gen;

        {
            std::unique_lock<std::mutex> lock(sender_mutex);
            sender_cv.wait(lock, [this] { return stop_sender || has_work; });

            if(stop_sender)
            {
                return;
            }

            wanted      = target;
            gen         = generation;
            has_work    = false;
        }

        /*-------------------------------------------------*\
        | One complete pass: every key whose wanted colour  |
        | differs from what the keyboard shows, biggest     |
        | change first. The pass is always finished, so     |
        | each frame looks coherent; frames that arrive     |
        | meanwhile are skipped and the next pass uses the  |
        | latest colours, so the last colour always wins    |
        \*-------------------------------------------------*/
        std::vector<Pending> todo;

        for(std::size_t led_idx = 0; led_idx < leds.size() && led_idx < wanted.size(); led_idx++)
        {
            if(leds[led_idx].value == RAPOO_V720_NO_KEY)
            {
                continue;
            }

            if(sent_valid[led_idx] && sent_colors[led_idx] == wanted[led_idx])
            {
                age[led_idx] = 0;
                continue;
            }

            unsigned int delta = 1024;

            if(sent_valid[led_idx])
            {
                RGBColor old    = sent_colors[led_idx];
                delta           = (unsigned int)(std::abs((int)RGBGetRValue(wanted[led_idx]) - (int)RGBGetRValue(old))
                                               + std::abs((int)RGBGetGValue(wanted[led_idx]) - (int)RGBGetGValue(old))
                                               + std::abs((int)RGBGetBValue(wanted[led_idx]) - (int)RGBGetBValue(old)));
            }

            age[led_idx]++;
            todo.push_back({ delta + age[led_idx] * 24, led_idx });
        }

        std::sort(todo.begin(), todo.end(), [](const Pending& x, const Pending& y) { return x.score > y.score; });

        bool failed = false;

        for(const Pending& p : todo)
        {
            RGBColor c = wanted[p.led];

            if(controller->SetKey((unsigned char)leds[p.led].value, RGBGetRValue(c), RGBGetGValue(c), RGBGetBValue(c)))
            {
                sent_colors[p.led]  = c;
                sent_valid[p.led]   = true;
                age[p.led]          = 0;
            }
            else
            {
                failed = true;
                break;
            }
        }

        if(failed)
        {
            /*---------------------------------------------*\
            | USB error: try again shortly instead of       |
            | spinning                                      |
            \*---------------------------------------------*/
            std::this_thread::sleep_for(std::chrono::milliseconds(50));

            std::lock_guard<std::mutex> lock(sender_mutex);
            has_work = true;
        }
    }
}

void RGBController_RapooV720::DeviceUpdateZoneLEDs(int /*zone*/)
{
    DeviceUpdateLEDs();
}

void RGBController_RapooV720::DeviceUpdateSingleLED(int /*led*/)
{
    DeviceUpdateLEDs();
}

void RGBController_RapooV720::DeviceUpdateMode()
{
    /*-----------------------------------------------------*\
    | Direct mode only                                      |
    \*-----------------------------------------------------*/
}
