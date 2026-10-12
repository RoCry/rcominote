#include <stdint.h>

/* Only a RAM marker. No board initialization, ROM calls, peripherals or IRQs. */
static volatile uint32_t initialized_cookie = 0x52434d34;
volatile uint32_t fixture_marker;

void fixture_main(void)
{
    fixture_marker = initialized_cookie;
    for (;;) {
        __asm__ volatile ("nop");
    }
}
