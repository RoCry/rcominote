/* Offline image fixture, not a validated CoMi BSP or loadable RAM helper. */
.syntax unified
.cpu cortex-m4
.thumb
.file "startup.S"

.section .vectors,"a",%progbits
.global vector_table
vector_table:
    .word __stack_top
    .word Reset_Handler
    .rept 78
    .word Default_Handler
    .endr

.section .text.Reset_Handler,"ax",%progbits
.thumb_func
.global Reset_Handler
Reset_Handler:
    cpsid i
    movs r0, #0
    msr control, r0
    isb
    ldr r0, =__stack_top
    msr msp, r0
    ldr r0, =__data_load
    ldr r1, =__data_start
    ldr r2, =__data_end
1:  cmp r1, r2
    bhs 2f
    ldr r3, [r0], #4
    str r3, [r1], #4
    b 1b
2:  ldr r1, =__bss_start
    ldr r2, =__bss_end
    movs r3, #0
3:  cmp r1, r2
    bhs 4f
    str r3, [r1], #4
    b 3b
4:  bl fixture_main
    b Default_Handler

.section .text.Default_Handler,"ax",%progbits
.thumb_func
Default_Handler:
    b Default_Handler
