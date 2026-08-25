//=============================================================================
//    S E N S I R I O N   AG,  Laubisruetistr. 50, CH-8712 Staefa, Switzerland
//=============================================================================
/// \file    sdp800.c (V1.0)
/// \author  RFU
/// \date    24-Jan-2016
/// \brief   Sensor Layer: Implementation of functions for sensor access.
//=============================================================================

#include "stdint.h"
#include "stdbool.h"
#include "sdp800.h"
#include "i2c_hal.h"

// Sensor Commands
typedef enum {
  /// Undefined dummy command.
  COMMAND_UNDEFINED                       = 0x0000,
  /// Start continous measurement                     \n
  /// Temperature compensation: Mass flow             \n
  /// Averaging: Average till read
  COMMAND_START_MEASURMENT_MF_AVERAGE     = 0x3603,
  /// Start continous measurement                     \n
  /// Temperature compensation: Mass flow             \n
  /// Averaging: None - Update rate 1ms
  COMMAND_START_MEASURMENT_MF_NONE        = 0x3608,
  /// Start continous measurement                     \n
  /// Temperature compensation: Differential pressure \n
  /// Averaging: Average till read
  COMMAND_START_MEASURMENT_DP_AVERAGE     = 0x3615,
  /// Start continous measurement                     \n
  /// Temperature compensation: Differential pressure \n
  /// Averaging: None - Update rate 1ms
  COMMAND_START_MEASURMENT_DP_NONE        = 0x361E,
  // Stop continuous measurement.
  COMMAND_STOP_CONTINOUS_MEASUREMENT      = 0x3FF9
} Command;

static Error ExecuteCommand(Command cmd);
static Error ReadMeasurementRawResults(int16_t* diffPressureTicks,
                                       int16_t* temperatureTicks,
                                       uint16_t* scaleFactor);
static Error ReadWordWithCrcCheck(uint16_t *value, bool ack);
static Error CheckCrc(const uint8_t data[], uint8_t size, uint8_t checksum);

static const float scaleFactorTemperature = 200;

static uint8_t _i2cAddress;

//-----------------------------------------------------------------------------
void Sdp800_Init(uint8_t i2cAddress){
  _i2cAddress = i2cAddress;
  I2c_Init();
}

//-----------------------------------------------------------------------------
Error Sdp800_StartContinousMeasurement(Sdp800TempComp  tempComp,
                                       Sdp800Averaging averaging)
{
  Error error;
  Command command = COMMAND_UNDEFINED;
  
  // determine command code
  switch(tempComp) {
    case SDP800_TEMPCOMP_MASS_FLOW:
      switch(averaging) {
        case SDP800_AVERAGING_TILL_READ:
          command = COMMAND_START_MEASURMENT_MF_AVERAGE;
          break;
        case SDP800_AVERAGING_NONE:
          command = COMMAND_START_MEASURMENT_MF_NONE;
          break;
      }
      break;
    case SDP800_TEMPCOMP_DIFFERNTIAL_PRESSURE:
      switch(averaging) {
        case SDP800_AVERAGING_TILL_READ:
          command = COMMAND_START_MEASURMENT_DP_AVERAGE;
          break;
        case SDP800_AVERAGING_NONE:
          command = COMMAND_START_MEASURMENT_DP_NONE;
          break;
      }
      break;
  }
  
  if(COMMAND_UNDEFINED != command) {
    error = ExecuteCommand(command);
    // wait 10 ms for startup
    DelayMicroSeconds(10000);
  } else {
    error = ERROR_IVALID_PARAMETER;
  }
  
  return error;
}

//-----------------------------------------------------------------------------
Error Sdp800_StopContinousMeasurement(void)
{
  return ExecuteCommand(COMMAND_STOP_CONTINOUS_MEASUREMENT);
}

//-----------------------------------------------------------------------------
Error Sdp800_ReadMeasurementResults(float* diffPressure, float* temperature)
{
  Error error;
  int16_t  diffPressureTicks;
  int16_t  temperatureTicks;
  uint16_t scaleFactorDiffPressure;
  
  error = ReadMeasurementRawResults(&diffPressureTicks, &temperatureTicks,
                                    &scaleFactorDiffPressure);
  
  if(ERROR_NONE == error) {
    *diffPressure = (float)diffPressureTicks / (float)scaleFactorDiffPressure;
    *temperature  = (float)temperatureTicks / scaleFactorTemperature;
  }
  
  return error;
}

//-----------------------------------------------------------------------------
Error Sdp800_SoftReset(void)
{
  Error error;
  
  // write a start condition
  I2c_StartCondition();

  // write the upper 8 bits of reset
  error = I2c_WriteByte(0x00);
  
  // write the lower 8 bits of reset
  if(ERROR_NONE == error) {
    error = I2c_WriteByte(0x06);
  }
  
  I2c_StopCondition();

  // wait 20 ms
  DelayMicroSeconds(20000); 

  return error;
}

//-----------------------------------------------------------------------------
static Error ReadMeasurementRawResults(int16_t*  diffPressureTicks,
                                       int16_t*  temperatureTicks,
                                       uint16_t* scaleFactor)
{
  Error error;
  
  // write a start condition
  I2c_StartCondition();

  // write the sensor I2C address with the read flag
  error = I2c_WriteByte(_i2cAddress << 1 | 0x01);
  
  // reas differnetial pressure ticks
  if(ERROR_NONE == error) {
    error = ReadWordWithCrcCheck((uint16_t*)diffPressureTicks, true);
  }
  
  // read temperature pressure ticks
  if(ERROR_NONE == error) {
    error = ReadWordWithCrcCheck((uint16_t*)temperatureTicks, true);
  }
  
  // read scale factor
  if(ERROR_NONE == error) {
    error = ReadWordWithCrcCheck(scaleFactor, false);
  }
  
  I2c_StopCondition();
  
  return error;
}

//-----------------------------------------------------------------------------
Error ExecuteCommand(Command cmd)
{
  Error error;
  
  // write a start condition
  I2c_StartCondition();

  // write the sensor I2C address with the write flag
  error = I2c_WriteByte(_i2cAddress << 1 | 0x00);

  // write the upper 8 bits of the command
  if(ERROR_NONE == error) {
    error = I2c_WriteByte(cmd >> 8);
  }
  
  // write the lower 8 bits of the command to the sensor
  if(ERROR_NONE == error) {
    error = I2c_WriteByte(cmd & 0xFF);
  }
  
  I2c_StopCondition();

  return error;
}

//-----------------------------------------------------------------------------
static Error ReadWordWithCrcCheck(uint16_t *value, bool ack)
{
  Error error;
  uint8_t bytes[2];
  uint8_t checksum;
 
  // read two data bytes and one checksum byte
  bytes[0] = I2c_ReadByte(ACK);
  bytes[1] = I2c_ReadByte(ACK);
  checksum = I2c_ReadByte(ack ? ACK : NACK);
  
  // verify checksum
  error = CheckCrc(bytes, 2, checksum);
  
  // combine the two bytes to a 16-bit value
  *value = (bytes[0] << 8) | bytes[1];
  
  return error;
}

//-----------------------------------------------------------------------------
static Error CheckCrc(const uint8_t data[], uint8_t size, uint8_t checksum)
{
  uint8_t crc = 0xFF;
  
  // calculates 8-Bit checksum with given polynomial 0x31 (x^8 + x^5 + x^4 + 1)
  for(int i = 0; i < size; i++) {
    crc ^= (data[i]);
    for(uint8_t bit = 8; bit > 0; --bit) {
      if(crc & 0x80) crc = (crc << 1) ^ 0x31;
      else           crc = (crc << 1);
    }
  }
  
  // verify checksum
  return (crc == checksum) ? ERROR_NONE : ERROR_CHECKSUM;
}
