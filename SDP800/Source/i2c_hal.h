//=============================================================================
//    S E N S I R I O N   AG,  Laubisruetistr. 50, CH-8712 Staefa, Switzerland
//=============================================================================
/// \file    i2c_hal.h (V1.0)
/// \author  RFU
/// \date    24-Jan-2016
/// \brief   I2C hardware abstraction layer 
//=============================================================================

#ifndef I2C_HAL_H
#define I2C_HAL_H

#include "system.h"

// I2C IO-Pins                         /* -- adapt the defines for your uC -- */
// SDA on port B, bit 9
#define SDA_LOW()  (GPIOB->BSRR = 0x02000000) // set SDA to low
#define SDA_OPEN() (GPIOB->BSRR = 0x00000200) // set SDA to open-drain
#define SDA_READ   (GPIOB->IDR  & 0x0200)     // read SDA

// SCL on port B, bit 8                /* -- adapt the defines for your uC -- */
#define SCL_LOW()  (GPIOB->BSRR = 0x01000000) // set SCL to low
#define SCL_OPEN() (GPIOB->BSRR = 0x00000100) // set SCL to open-drain
#define SCL_READ   (GPIOB->IDR  & 0x0100)     // read SCL

/// Enumearation for I2C acknowledge.
typedef enum{
  ACK    = 0,
  NACK   = 1,
}etI2cAck;

//-----------------------------------------------------------------------------
/// \brief  Initializes the ports for I2C interface.
void I2c_Init(void);

//-----------------------------------------------------------------------------
/// \brief  Writes a start condition on I2C-Bus.
///                _____                         \n
///         SDA:        |_____                   \n
//                 _______                       \n
//          SCL:          |___
/// \remark Timing (delay) may have to be changed for different microcontroller.
void I2c_StartCondition(void);

//-----------------------------------------------------------------------------
/// \brief  Writes a stop condition on I2C-Bus.  \n
///                      _____                   \n
///         SDA:   _____|                        \n
//                     _______                   \n
//          SCL:   ___|
/// \remark Timing (delay) may have to be changed for different microcontroller.
void I2c_StopCondition(void);

//-----------------------------------------------------------------------------
/// \brief  Writes a byte to I2C-Bus and checks acknowledge.
/// \param  txByte  Transmit byte
/// \return ERROR_ACK  = no acknowledgment from sensor
//          ERROR_NONE = no error
/// \remark Timing (delay) may have to be changed for different microcontroller.
Error I2c_WriteByte(uint8_t txByte);

//-----------------------------------------------------------------------------
/// \brief  Reads a byte on I2C-Bus.
/// \param  ack  Acknowledge: ACK or NO_ACK
/// \return Received byte.
/// \remark Timing (delay) may have to be changed for different microcontroller.
uint8_t I2c_ReadByte(etI2cAck ack);

#endif
