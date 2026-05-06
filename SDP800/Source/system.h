//=============================================================================
//    S E N S I R I O N   AG,  Laubisruetistr. 50, CH-8712 Staefa, Switzerland
//=============================================================================
/// \file    system.h (V1.0)
/// \author  RFU
/// \date    24-Jan-2016
/// \brief   System functions, global definitions
//=============================================================================

#ifndef SYSTEM_H
#define SYSTEM_H

#include "stdint.h"

//-----------------------------------------------------------------------------
/// \brief Error codes
typedef enum {
  ERROR_NONE              = 0x00, // no error
  ERROR_ACK               = 0x01, // no acknowledgment error
  ERROR_CHECKSUM          = 0x02, // checksum mismatch error
  ERROR_IVALID_PARAMETER  = 0xFF, // invalid parameter
} Error;

//-----------------------------------------------------------------------------
/// \brief Initializes the system.
void SystemInit(void);

//-----------------------------------------------------------------------------
/// \brief  Wait function for small delays.
/// \param  nbrOfUs  Wait x times approx. one micro second (fcpu = 8MHz).
/// \remark Smallest delay is approximately 15us due to function call
void DelayMicroSeconds(uint32_t nbrOfUs);

#endif /* SYSTEM_H */
