/* Generated from pinned LARK loader DWARF; NOT a CoMi BSP.
 * Only field layouts and IRQ values. No MMIO bases, bit semantics, startup or pin map.
 * See docs/lark-register-recovery.md. Do not edit generated files. */
#ifndef RCOMINOTE_LARK_REGISTER_LAYOUTS_H
#define RCOMINOTE_LARK_REGISTER_LAYOUTS_H
#include <stdint.h>

/* Source CMUA_Type, 36 bytes. */
typedef struct {
    const volatile uint32_t RESERVED[7]; /* +0x0 */
    volatile uint32_t AVDDLDO_CTL; /* +0x1c */
    volatile uint32_t COREPLL_CTL; /* +0x20 */
} rc_lark_CMUA;

/* Source CMUD_Type, 280 bytes. */
typedef struct {
    volatile uint32_t SYSCLK; /* +0x0 */
    volatile uint32_t DEVCLKEN0; /* +0x4 */
    volatile uint32_t DEVCLKEN1; /* +0x8 */
    const volatile uint32_t RESERVED[5]; /* +0xc */
    volatile uint32_t SPICLK[4]; /* +0x20 */
    volatile uint32_t DECLK; /* +0x30 */
    volatile uint32_t LCDCLK; /* +0x34 */
    const volatile uint32_t RESERVED1[2]; /* +0x38 */
    volatile uint32_t TIMERCLK[5]; /* +0x40 */
    const volatile uint32_t RESERVED2[11]; /* +0x54 */
    volatile uint32_t I2CCLK[2]; /* +0x80 */
    const volatile uint32_t RESERVED3[10]; /* +0x88 */
    volatile uint32_t MEMCLKEN0; /* +0xb0 */
    volatile uint32_t MEMCLKEN1; /* +0xb4 */
    const volatile uint32_t RESERVED4[2]; /* +0xb8 */
    volatile uint32_t MEMCLKSRC0; /* +0xc0 */
    volatile uint32_t MEMCLKSRC1; /* +0xc4 */
    const volatile uint32_t RESERVED5[14]; /* +0xc8 */
    volatile uint32_t SPIMTCLK[2]; /* +0x100 */
    const volatile uint32_t RESERVED6[2]; /* +0x108 */
    volatile uint32_t I2CMTCLK[2]; /* +0x110 */
} rc_lark_CMUD;

/* Source GPIO_Type, 784 bytes. */
typedef struct {
    volatile uint32_t JTAG; /* +0x0 */
    volatile uint32_t CTL[78]; /* +0x4 */
    const volatile uint32_t RESERVED[49]; /* +0x13c */
    volatile uint32_t ODAT[3]; /* +0x200 */
    const volatile uint32_t RESERVED1; /* +0x20c */
    volatile uint32_t BSR[3]; /* +0x210 */
    const volatile uint32_t RESERVED2; /* +0x21c */
    volatile uint32_t BRR[3]; /* +0x220 */
    const volatile uint32_t RESERVED3; /* +0x22c */
    volatile uint32_t IDAT[3]; /* +0x230 */
    const volatile uint32_t RESERVED4; /* +0x23c */
    volatile uint32_t PD[3]; /* +0x240 */
    const volatile uint32_t RESERVED5[45]; /* +0x24c */
    volatile uint32_t WIOCTL[4]; /* +0x300 */
} rc_lark_GPIO;

/* Source MEM_Type, 784 bytes. */
typedef struct {
    volatile uint32_t CTL; /* +0x0 */
    const volatile uint32_t RESERVED; /* +0x4 */
    volatile uint32_t CPU_ERR_ADDR; /* +0x8 */
    const volatile uint32_t RESERVED1[5]; /* +0xc */
    volatile uint32_t CTL2; /* +0x20 */
    const volatile uint32_t RESERVED2[183]; /* +0x24 */
    volatile uint32_t SPICACHE_MAPPING_ADDR0; /* +0x300 */
    volatile uint32_t SPICACHE_ADDR0_ENTRY; /* +0x304 */
    volatile uint32_t SPICACHE_MAPPING_ADDR1; /* +0x308 */
    volatile uint32_t SPICACHE_ADDR1_ENTRY; /* +0x30c */
} rc_lark_MEM;

/* Source PMU_Type, 288 bytes. */
typedef struct {
    volatile uint32_t VOUT_CTL0; /* +0x0 */
    volatile uint32_t VOUT_CTL1_S1; /* +0x4 */
    volatile uint32_t VOUT_CTL1_S2; /* +0x8 */
    volatile uint32_t VOUT_CTL1_S3; /* +0xc */
    volatile uint32_t PMU_DET; /* +0x10 */
    const volatile uint32_t RESERVED[3]; /* +0x14 */
    volatile uint32_t DCDC_VC18_CTL; /* +0x20 */
    volatile uint32_t DCDC_VC12_CTL; /* +0x24 */
    volatile uint32_t DCDC_VDD_CTL; /* +0x28 */
    const volatile uint32_t RESERVED1; /* +0x2c */
    volatile uint32_t PWRGATE_DIG; /* +0x30 */
    volatile uint32_t PWRGATE_DIG_ACK; /* +0x34 */
    volatile uint32_t PWRGATE_RAM; /* +0x38 */
    volatile uint32_t PWRGATE_RAM_ACK; /* +0x3c */
    volatile uint32_t PMU_INTMASK; /* +0x40 */
    const volatile uint32_t RESERVED2[47]; /* +0x44 */
    volatile uint32_t CHG_CTL_SVCC; /* +0x100 */
    volatile uint32_t BDG_CTL_SVCC; /* +0x104 */
    volatile uint32_t SYSTEM_SET_SVCC; /* +0x108 */
    volatile uint32_t POWER_CTL_SVCC; /* +0x10c */
    volatile uint32_t WAKE_CTL_SVCC; /* +0x110 */
    volatile uint32_t WAKE_PD_SVCC; /* +0x114 */
    volatile uint32_t COUNTER8HZ_SVCC; /* +0x118 */
    volatile uint32_t ALARM8HZ_SVCC; /* +0x11c */
} rc_lark_PMU;

/* Source RMU_Type, 8 bytes. */
typedef struct {
    volatile uint32_t MRCR0; /* +0x0 */
    volatile uint32_t MRCR1; /* +0x4 */
} rc_lark_RMU;

/* Source RTC_Type, 36 bytes. */
typedef struct {
    const volatile uint32_t RESERVED[8]; /* +0x0 */
    volatile uint32_t WD; /* +0x20 */
} rc_lark_RTC;

/* Source SPI0CACHE_Type, 56 bytes. */
typedef struct {
    volatile uint32_t CTL; /* +0x0 */
    volatile uint32_t INVALIDATE; /* +0x4 */
    const volatile uint32_t RESERVED[2]; /* +0x8 */
    const volatile uint32_t TOTAL_MISS; /* +0x10 */
    const volatile uint32_t TOTAL_HIT; /* +0x14 */
    volatile uint32_t PROFILE_IDX_START; /* +0x18 */
    volatile uint32_t PROFILE_IDX_END; /* +0x1c */
    const volatile uint32_t RANGE_IDX_MISS; /* +0x20 */
    const volatile uint32_t RANGE_IDX_HIT; /* +0x24 */
    volatile uint32_t PROFILE_START; /* +0x28 */
    volatile uint32_t PROFILE_END; /* +0x2c */
    const volatile uint32_t RANGE_MISS; /* +0x30 */
    const volatile uint32_t RANGE_HIT; /* +0x34 */
} rc_lark_SPI0CACHE;

/* Source SPI0_Type, 24 bytes. */
typedef struct {
    volatile uint32_t CTL; /* +0x0 */
    volatile uint32_t STA; /* +0x4 */
    volatile uint32_t TXDAT; /* +0x8 */
    const volatile uint32_t RXDAT; /* +0xc */
    volatile uint32_t BC; /* +0x10 */
    volatile uint32_t SEED; /* +0x14 */
} rc_lark_SPI0;

/* Source SPI1CACHE_Type, 68 bytes. */
typedef struct {
    volatile uint32_t CTL; /* +0x0 */
    volatile uint32_t OPERATE; /* +0x4 */
    volatile uint32_t CPU_UNCACHE_START; /* +0x8 */
    volatile uint32_t CPU_UNCACHE_END; /* +0xc */
    const volatile uint32_t M4F_MISS; /* +0x10 */
    const volatile uint32_t M4F_HIT; /* +0x14 */
    volatile uint32_t M4F_WRITEBACK; /* +0x18 */
    const volatile uint32_t RESERVED[3]; /* +0x1c */
    const volatile uint32_t DMA_MISS; /* +0x28 */
    const volatile uint32_t DMA_HIT; /* +0x2c */
    volatile uint32_t DMA_WRITEBACK; /* +0x30 */
    const volatile uint32_t RESERVED1[2]; /* +0x34 */
    volatile uint32_t PROFILE_START; /* +0x3c */
    volatile uint32_t PROFILE_END; /* +0x40 */
} rc_lark_SPI1CACHE;

/* Source SPI1_Type, 60 bytes. */
typedef struct {
    volatile uint32_t CTL; /* +0x0 */
    volatile uint32_t STA; /* +0x4 */
    volatile uint32_t TXDAT; /* +0x8 */
    const volatile uint32_t RXDAT; /* +0xc */
    volatile uint32_t BC; /* +0x10 */
    const volatile uint32_t RESERVED; /* +0x14 */
    volatile uint32_t DDR_MODE_CTL; /* +0x18 */
    const volatile uint32_t RESERVED1; /* +0x1c */
    volatile uint32_t DDR_CMD; /* +0x20 */
    volatile uint32_t DDR_START; /* +0x24 */
    volatile uint32_t DDR_STATUS; /* +0x28 */
    volatile uint32_t DDR_ADDR0; /* +0x2c */
    volatile uint32_t DDR_ADDR1; /* +0x30 */
    volatile uint32_t DDR_TRXLEN; /* +0x34 */
    volatile uint32_t CLKGATING; /* +0x38 */
} rc_lark_SPI1;

/* Source UART_Type, 16384 bytes. */
typedef struct {
    volatile uint32_t CTL; /* +0x0 */
    const volatile uint32_t RXDAT; /* +0x4 */
    volatile uint32_t TXDAT; /* +0x8 */
    volatile uint32_t STA; /* +0xc */
    volatile uint32_t BR; /* +0x10 */
    const volatile uint32_t RESERVED[4091]; /* +0x14 */
} rc_lark_UART;

/* Source IRQn_Type size=1; values only, no enum ABI typedef. */
enum {
    RC_LARK_Reset_IRQn = -15,
    RC_LARK_NonMaskableInt_IRQn = -14,
    RC_LARK_HardFault_IRQn = -13,
    RC_LARK_MemoryManagement_IRQn = -12,
    RC_LARK_BusFault_IRQn = -11,
    RC_LARK_UsageFault_IRQn = -10,
    RC_LARK_SVCall_IRQn = -5,
    RC_LARK_DebugMonitor_IRQn = -4,
    RC_LARK_PendSV_IRQn = -2,
    RC_LARK_SysTick_IRQn = -1,
    RC_LARK_WD_2HZ_IRQn = 1,
    RC_LARK_TIMER0_IRQn = 2,
    RC_LARK_TIMER1_IRQn = 3,
    RC_LARK_TIMER2_IRQn = 4,
    RC_LARK_TIMER3_IRQn = 5,
    RC_LARK_TIMER4_IRQn = 6,
    RC_LARK_RTC_IRQn = 7,
    RC_LARK_SPI0_IRQn = 12,
    RC_LARK_SPI1_IRQn = 13,
    RC_LARK_SPI2_IRQn = 14,
    RC_LARK_SPI3_IRQn = 15,
    RC_LARK_I2C0_IRQn = 18,
    RC_LARK_I2C1_IRQn = 19,
    RC_LARK_UART0_IRQn = 22,
    RC_LARK_UART1_IRQn = 23,
    RC_LARK_UART2_IRQn = 24,
    RC_LARK_DMA0_IRQn = 27,
    RC_LARK_DMA1_IRQn = 28,
    RC_LARK_DMA2_IRQn = 29,
    RC_LARK_DMA3_IRQn = 30,
    RC_LARK_DMA4_IRQn = 31,
    RC_LARK_DMA5_IRQn = 32,
    RC_LARK_DMA6_IRQn = 33,
    RC_LARK_DMA7_IRQn = 34,
    RC_LARK_DMA8_IRQn = 35,
    RC_LARK_DMA9_IRQn = 36,
    RC_LARK_GPIO_IRQn = 37,
    RC_LARK_LCD_IRQn = 43,
    RC_LARK_DE_IRQn = 49,
    RC_LARK_BT_IRQn = 56,
    RC_LARK_ANCDSP0_IRQn = 57,
    RC_LARK_TWS_IRQn = 58,
    RC_LARK_ANCDSP1_IRQn = 59,
    RC_LARK_SPI0MT_IRQn = 60,
    RC_LARK_SPI1MT_IRQn = 61,
    RC_LARK_I2C0MT_IRQn = 62,
    RC_LARK_I2C1MT_IRQn = 63,
};

#endif
