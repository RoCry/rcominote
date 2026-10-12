ENTRY(Reset_Handler)

/* Observed original image addresses, not a claim of currently free memory. */
MEMORY
{
    IMAGE (rx) : ORIGIN = 0x10000200, LENGTH = 0x1000
    RAM (rw) : ORIGIN = 0x01001b40, LENGTH = 0x800
}
__stack_top = 0x01002b40;
__stack_bottom = 0x01002340;

SECTIONS
{
    .vectors : { KEEP(*(.vectors)) } > IMAGE
    .text : { *(.text*) *(.rodata*) . = ALIGN(4); } > IMAGE
    .data :
    {
        __data_start = .;
        *(.data*)
        . = ALIGN(4);
        __data_end = .;
    } > RAM AT> IMAGE
    __data_load = LOADADDR(.data);
    .bss (NOLOAD) :
    {
        __bss_start = .;
        *(.bss*) *(COMMON)
        . = ALIGN(4);
        __bss_end = .;
    } > RAM
    /DISCARD/ : { *(.comment) *(.note*) *(.ARM.exidx*) *(.ARM.extab*) }
}
ASSERT(SIZEOF(.vectors) == 320, "Expected 80 original-style vector slots")
ASSERT(__bss_end <= __stack_bottom, "Data must not overlap fixture stack")
ASSERT((__data_load & 3) == 0, "Data load must be word aligned")
