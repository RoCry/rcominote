#include "comi_uart.h"

#define UART_RXDAT (*(volatile uint32_t *)(COMI_UART0_BASE + 4u))
#define UART_TXDAT (*(volatile uint32_t *)(COMI_UART0_BASE + 8u))
#define UART_STAT (*(volatile uint32_t *)(COMI_UART0_BASE + 12u))
#define UART_RX_EMPTY (UINT32_C(1) << 5)
#define UART_TX_FULL (UINT32_C(1) << 6)

enum comi_uart_result comi_uart0_putc(uint8_t value, uint32_t polls)
{
    if (polls == 0u) {
        return COMI_UART_INVALID_ARGUMENT;
    }
    while (polls-- != 0u) {
        if ((UART_STAT & UART_TX_FULL) == 0u) {
            UART_TXDAT = value;
            return COMI_UART_OK;
        }
    }
    return COMI_UART_TIMEOUT;
}

enum comi_uart_result comi_uart0_getc(uint8_t *value, uint32_t polls)
{
    if (value == 0 || polls == 0u) {
        return COMI_UART_INVALID_ARGUMENT;
    }
    while (polls-- != 0u) {
        if ((UART_STAT & UART_RX_EMPTY) == 0u) {
            *value = (uint8_t)UART_RXDAT;
            return COMI_UART_OK;
        }
    }
    return COMI_UART_TIMEOUT;
}
