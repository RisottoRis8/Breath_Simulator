//=============================================================================
//    S E N S I R I O N   AG,  Laubisruetistr. 50, CH-8712 Staefa, Switzerland
//=============================================================================
/// \file    main.c
/// \author  RFU
/// \date    24-Jan-2016
/// \brief   This code shows how to implement the basic commands for the SDP3x
///          sensor chip.
///          Due to compatibility reasons the I2C interface is implemented as
///          "bit-banging" on normal I/O's. This code is written for an easy
///          understanding and is neither optimized for speed nor code size.
//-----------------------------------------------------------------------------
// Porting to a different microcontroller (uC):
//   - change the port functions / definitions for your uC    in i2c_hal.h/.c
//   - adapt the timing of the delay function for your uC     in system.c
//   - adapt the SystemInit()                                 in system.c
//   - change the uC register definition file <stm32f10x.h>   in system.h
//
//   Sensor        STM32-discovery board
//   ------        -------------------------
//      SDA <----> PB9 (pull-up resistor to VDD)
//      GND <----> GND
//      VDD <----> 3V3
//      SCL <----> PB8 (pull-up resistor to VDD)
//=============================================================================

#include <stm32f10x.h> 
#include "system.h"
#include "sdp800.h"

static void Leds_Init(void);
static void LedBlueOn(void);
static void LedBlueOff(void);
static void LedGreenOn(void);
static void LedGreenOff(void);

int main(void)
{
	Error error;
	float diffPressure;
	float temperature;
  
  Leds_Init();
	Sdp800_Init(0x25); // initialize sensor module with address 0x25

  while(1) {
    // reset the sensor
    Sdp800_SoftReset();
    
    // start continous measurement
    error = Sdp800_StartContinousMeasurement(SDP800_TEMPCOMP_MASS_FLOW,
                                             SDP800_AVERAGING_TILL_READ);
    
    // read measurement results as long as no error occurs
    while(ERROR_NONE == error) {
      // wait 1 ms
      DelayMicroSeconds(1000); 
      
      // read measurement results
      error = Sdp800_ReadMeasurementResults(&diffPressure, &temperature);
      if(error != ERROR_NONE) break;
      
      // show with the green LED that no error occurred
      LedGreenOn();
      
      // indicate pressure difference with the blue LED
      if(diffPressure > 1.0f || diffPressure < -1.0f) {
        LedBlueOn();
      } else {
        LedBlueOff();
      }
    }
    
    // on error: flash green LED
    LedGreenOn();
    DelayMicroSeconds(100000); // wait 100 ms
    LedGreenOff();
    DelayMicroSeconds(100000); // wait 100 ms
  }
}

//-----------------------------------------------------------------------------
static void Leds_Init(void)
{
  RCC->APB2ENR |= 0x00000010; // I/O port C clock enabled
  GPIOC->CRH   &= 0xFFFFFF00; // Set general purpose output mode for LEDs
  GPIOC->CRH   |= 0x00000011; //
  GPIOC->BSRR   = 0x03000000; // LEDs off
}

//-----------------------------------------------------------------------------
static void LedBlueOn(void)
{
  GPIOC->BSRR = 0x00000100;
}

//-----------------------------------------------------------------------------
static void LedBlueOff(void)
{
  GPIOC->BSRR = 0x01000000;
}

//-----------------------------------------------------------------------------
static void LedGreenOn(void)
{
  GPIOC->BSRR = 0x00000200;
}

//-----------------------------------------------------------------------------
static void LedGreenOff(void)
{
  GPIOC->BSRR = 0x02000000;
}
