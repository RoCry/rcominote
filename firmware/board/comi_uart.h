#ifndef RCOMINOTE_COMI_UART_H
#define RCOMINOTE_COMI_UART_H

#include <stdint.h>

/* FW010004 descriptor/config and instruction evidence; logical GPIO numbers. */
#define COMI_UART0_BASE UINT32_C(0x40038000)
#define COMI_UART0_TX_GPIO 28u
#define COMI_UART0_RX_GPIO 29u
/* Early packaged configuration; later live GPIO28 CTRL read was 0x1805. */
#define COMI_UART0_PINMUX UINT32_C(0x4125)
#define COMI_UART0_PACKAGED_BAUD 2000000u

enum comi_uart_result {
    COMI_UART_OK = 0,
    COMI_UART_TIMEOUT = -1,
    COMI_UART_INVALID_ARGUMENT = -2,
};

/* UART clock, mux, baud and CTRL must already be initialized by the caller.
 * polls bounds status-register reads, not elapsed time. No clock/reset changes.
 * Not linked into the minimal ACTH fixture; never tested on the device.
 */
enum comi_uart_result comi_uart0_putc(uint8_t value, uint32_t polls);
enum comi_uart_result comi_uart0_getc(uint8_t *value, uint32_t polls);

#endif
