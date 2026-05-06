//=============================================================================
//    S E N S I R I O N   AG,  Laubisruetistr. 50, CH-8712 Staefa, Switzerland
//=============================================================================
/// \file    i2c_hal.c (V1.0)
/// \author  RFU
/// \date    24-Jan-2016
/// \brief   I2C hardware abstraction layer
//=============================================================================

#include <stm32f10x.h> 
#include "i2c_hal.h"

//-----------------------------------------------------------------------------
void I2c_Init(void)                      /* -- adapt the init for your uC -- */
{                    
  RCC->APB2ENR |= 0x00000008;  // I/O port B clock enabled
  
  GPIOB->CRH   &= 0xFFFFFF00;  // set open-drain output for SDA and SCL
  GPIOB->CRH   |= 0x00000055;  // 
  
  SDA_OPEN();                  // I2C-bus idle mode SDA released
  SCL_OPEN();                  // I2C-bus idle mode SCL released
}

//-----------------------------------------------------------------------------
void I2c_StartCondition(void)
{
  SDA_OPEN();
  DelayMicroSeconds(1);
  SCL_OPEN();
  DelayMicroSeconds(1);
  SDA_LOW();
  DelayMicroSeconds(10);  // hold time start condition (t_HD;STA)
  SCL_LOW();
  DelayMicroSeconds(10);
}

//-----------------------------------------------------------------------------
void I2c_StopCondition(void)
{
  SCL_LOW();
  DelayMicroSeconds(1);
  SDA_LOW();
  DelayMicroSeconds(1);
  SCL_OPEN();
  DelayMicroSeconds(10);  // set-up time stop condition (t_SU;STO)
  SDA_OPEN();
  DelayMicroSeconds(10);
}

//-----------------------------------------------------------------------------
Error I2c_WriteByte(uint8_t txByte)
{
  uint8_t mask;
  Error error = ERROR_NONE;
  for(mask = 0x80; mask > 0; mask >>= 1) { // shift bit for masking (8 times)
    if((mask & txByte) == 0) SDA_LOW();    // masking txByte & write to SDA-Line
    else                     SDA_OPEN();   
    DelayMicroSeconds(1);                  // data set-up time (t_SU;DAT)
    SCL_OPEN();                            // generate clock pulse on SCL
    DelayMicroSeconds(5);                  // SCL high time (t_HIGH)
    SCL_LOW();                             
    DelayMicroSeconds(1);                  // data hold time(t_HD;DAT)
  }                                        
  SDA_OPEN();                              // release SDA-line
  SCL_OPEN();                              // clk #9 for ack
  DelayMicroSeconds(1);                    // data set-up time (t_SU;DAT)
  if(SDA_READ) error = ERROR_ACK;          // check ack from i2c slave
  SCL_LOW();                               
  DelayMicroSeconds(20);                   // wait to see byte package on scope
  return error;                            // return error code
}

//-----------------------------------------------------------------------------
uint8_t I2c_ReadByte(etI2cAck ack)
{
  uint8_t mask;
  uint8_t rxByte = ERROR_NONE;
  SDA_OPEN();                              // release SDA-line
  for(mask = 0x80; mask > 0; mask >>= 1) { // shift bit for masking (8 times)
    SCL_OPEN();                            // generate clock pulse on SCL
    DelayMicroSeconds(1);                  // data set-up time (t_SU;DAT)
		while(SCL_READ == 0){}                 // wait while hold master
    DelayMicroSeconds(3);                  // SCL high time (t_HIGH)
    if(SDA_READ) rxByte = rxByte | mask;   // read bit
    SCL_LOW();                             
    DelayMicroSeconds(1);                  // data hold time(t_HD;DAT)
  }                                        
  if(ack == ACK) SDA_LOW();                // send acknowledge if necessary
  else           SDA_OPEN();               
  DelayMicroSeconds(1);                    // data set-up time (t_SU;DAT)
  SCL_OPEN();                              // clk #9 for ack
  DelayMicroSeconds(5);                    // SCL high time (t_HIGH)
  SCL_LOW();                               
  SDA_OPEN();                              // release SDA-line
  DelayMicroSeconds(20);                   // wait to see byte package on scope
  return rxByte;                           // return error code
}
