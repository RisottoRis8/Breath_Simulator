/* USER CODE BEGIN Header */
/**
  * @file           : main.c
  * @brief          : Lettura continua SDP810 con comandi START/STOP
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include "stdio.h"
#include "string.h"
#include "stdbool.h"
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
I2C_HandleTypeDef hi2c1;

TIM_HandleTypeDef htim1;
TIM_HandleTypeDef htim6;
TIM_HandleTypeDef htim7;

UART_HandleTypeDef huart1;
UART_HandleTypeDef huart2;

/* USER CODE BEGIN PV */
#define SDP810_ADDR (0x25 << 1)  // L'HAL STM32 richiede l'indirizzo a 8-bit (0x4A)

// Variabili per la ricezione UART
uint8_t rx_byte;
char rx_buffer[16];
uint8_t rx_index = 0;

// Stato del sistema
volatile bool is_measuring = false;
volatile bool cmd_received = false;
volatile bool is_ramping = false;
uint8_t duty_cycle= 30;
uint8_t divider = 0;
uint8_t message_divider = 0;
bool is_downing = false;
bool allowed_tick = false;
bool temporizzatore = false;
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_USART2_UART_Init(void);
static void MX_USART1_UART_Init(void);
static void MX_I2C1_Init(void);
static void MX_TIM6_Init(void);
static void MX_TIM1_Init(void);
static void MX_TIM7_Init(void);
/* USER CODE BEGIN PFP */
void SDP810_Start(void);
void SDP810_Stop(void);
/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

// Invia il comando per iniziare le misurazioni continue
void SDP810_Start(void) {
    uint8_t cmd[2] = {0x36, 0x15};
    HAL_I2C_Master_Transmit(&hi2c1, SDP810_ADDR, cmd, 2, 100);
    is_measuring = true;
    HAL_UART_Transmit(&huart1, (uint8_t*)"Misurazione AVVIATA\r\n", 21, 100);
}

// Invia il comando per fermare le misurazioni
void SDP810_Stop(void) {
    uint8_t cmd[2] = {0x3F, 0xF9};
    HAL_I2C_Master_Transmit(&hi2c1, SDP810_ADDR, cmd, 2, 100);
    is_measuring = false;
    HAL_UART_Transmit(&huart1, (uint8_t*)"Misurazione FERMATA\r\n", 21, 100);
}

// Assicurati che l'handle del timer 1 sia visibile
extern TIM_HandleTypeDef htim1;

void motor_Start(int speed, int dir) {
    // 1. Vincola la velocità ai limiti 0-255 per sicurezza
    if (speed > 255) speed = 255;
    if (speed < 0) speed = 0;

    // 2. Imposta la direzione (PB4)
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_4, (dir == 1) ? GPIO_PIN_SET : GPIO_PIN_RESET);

    // 3. Imposta il duty cycle del PWM sul Timer 1 Canale 4
    __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_4, speed);

    // 4. Avvia la generazione del segnale PWM (PA11)
    HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_4);

    // 5. Attiva l'Enable del motore (PB5)
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_5, GPIO_PIN_SET);
}

void motor_Stop(void) {
    // 1. Disattiva l'Enable del motore (PB5) per togliere potenza
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_5, GPIO_PIN_RESET);

    // 2. Ferma il PWM
    HAL_TIM_PWM_Stop(&htim1, TIM_CHANNEL_4);

    // 3. Azzera il registro di comparazione per sicurezza
    __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_4, 0);
}


// Interrupt Callback per la ricezione UART
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart) {
    if (huart->Instance == USART1) {
        // Se riceve un invio (Carriage Return o Line Feed)
        if (rx_byte == '\n' || rx_byte == '\r') {
            if (rx_index > 0) {
                rx_buffer[rx_index] = '\0'; // Chiude la stringa
                cmd_received = true;        // Segnala al main loop che c'è un comando
            }
        } else {
            // Salva il carattere nel buffer (evitando overflow)
            if (rx_index < 15) {
                rx_buffer[rx_index++] = rx_byte;
            }
        }
        // Riarma l'interrupt per il prossimo carattere
        HAL_UART_Receive_IT(&huart1, &rx_byte, 1);
    }
}
/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */
	int mode = -1;

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */
  int motorSpeed = 0;

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_USART2_UART_Init();
  MX_USART1_UART_Init();
  MX_I2C1_Init();
  MX_TIM6_Init();
  MX_TIM1_Init();
  MX_TIM7_Init();
  /* USER CODE BEGIN 2 */
  // Messaggio di benvenuto
  char msg[] = "Sistema pronto.\r\n";
  HAL_UART_Transmit(&huart1, (uint8_t*)msg, strlen(msg), 100);

  // Riarmo iniziale della ricezione UART 1 via interrupt
  HAL_UART_Receive_IT(&huart1, &rx_byte, 1);

  // Assicurati che il sensore sia fermo all'avvio
  SDP810_Stop();
  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
      // 1. Gestione dei comandi ricevuti da UART NON SICRONIZZATO.
      if (cmd_received) {
          cmd_received = false; // Abbassa la flag

          if (strncmp(rx_buffer, "START", 5) == 0) { //DA SOSTITUIRE CON INIT. AVVIA SENSORI E TEMPORIZZAZIONE
              SDP810_Start();
              HAL_TIM_Base_Start_IT(&htim7);
          }

          else if (strncmp(rx_buffer, "STOP", 4) == 0) {
              SDP810_Stop();
          }


          else if (sscanf(rx_buffer, "Mode %d", &mode)==1){
        	  int motorDir = 0;
        	  switch (mode){
        	  case 0: //linear
        		  break;
        	  case 1: //sine
        		  break;
        	  case 2: //cal
        		  break;
        	  case 3: //push, replaces STRM
        		  if (sscanf(rx_buffer, "Mode 3 %d %d", &motorSpeed, &motorDir) == 2){
                      motor_Start(motorSpeed, motorDir);
                      HAL_UART_Transmit(&huart1, (uint8_t*)"Motore AVVIATO\r\n", 16, 100);}
        		  break;
        	  case 4: //home
        		  break;
        	  case 127: //self test
        		  break;
        	  default:
        		  HAL_UART_Transmit(&huart1, (uint8_t*)"Modalità sconosciuta\r\n", strlen("Modalità sconosciuta\r\n"), 100);
        		  break;
          }

          }



          // COMANDI LEGACY DA RIMUOVERE
          else if (strncmp(rx_buffer, "STRM", 4) == 0) {
              int motorDir = 0;
              // Legge velocità e direzione. Ritorna il numero di parametri letti con successo.
              if (sscanf(rx_buffer, "STRM %d %d", &motorSpeed, &motorDir) == 2) {
                  motor_Start(motorSpeed, motorDir);
                  HAL_UART_Transmit(&huart1, (uint8_t*)"Motore AVVIATO\r\n", 16, 100);
              } else {
                  HAL_UART_Transmit(&huart1, (uint8_t*)"Errore sintassi: usa STRM <vel> <dir>\r\n", 39, 100);
              }
          }


          else if (strncmp(rx_buffer, "STPM", 4) == 0) {
              motor_Stop();
              is_ramping=false;
              HAL_UART_Transmit(&huart1, (uint8_t*)"Motore FERMATO\r\n", 16, 100);
          }


          else if (strncmp(rx_buffer, "RAMP", 4) == 0) {
        	  is_ramping = true;
        	  duty_cycle = 30;
              HAL_UART_Transmit(&huart1, (uint8_t*)"Motore RAMPA\r\n", 16, 100);
          }


          else {
        	  HAL_UART_Transmit(&huart1, (uint8_t*)rx_buffer, strlen(rx_buffer), 100);
        	  HAL_UART_Transmit(&huart1, (uint8_t*)" : Comando sconosciuto\r\n", strlen(" : Comando sconosciuto\r\n"), 100);
          }



          rx_index = 0; // Resetta il buffer per il prossimo comando
      }



      if (allowed_tick){

      // 2. Acquisizione dati I2C (se lo stato è attivo)
      if (is_measuring && allowed_tick) {
          allowed_tick = false;



    	  //DA METTERE DENTRO UNA FUNZIONE SEND_SDP
          uint8_t data[9];
          char out_buf[64];
          // Richiede 9 byte di risposta dal sensore
          if (HAL_I2C_Master_Receive(&hi2c1, SDP810_ADDR, data, 9, 100) == HAL_OK) {

              int16_t dp_raw = (data[0] << 8) | data[1];
              int16_t scale_factor = (data[6] << 8) | data[7];

              if (scale_factor != 0) {
                  float pressure = (float)dp_raw / (float)scale_factor;

                  // Formatta la stringa (richiede l'abilitazione dei float nelle impostazioni STM32)
                  message_divider = (message_divider +1);

                  if (message_divider == 3){
                	  message_divider = 0;
                  if (pressure > 0.05 || pressure <-0.05){
                	  sprintf(out_buf, "SNSR %.2f %d 0\r\n", pressure, message_divider);
                  }
                  else{
                	  sprintf(out_buf, "SNSR 0 0 0\r\n");
                  }
                  // Trasmetti su entrambe le porte
                    HAL_UART_Transmit(&huart1, (uint8_t*)out_buf, strlen(out_buf), 100);
                  }


              }
          } else {
              HAL_UART_Transmit(&huart1, (uint8_t*)"Errore Lettura\r\n", 16, 100);
          }
          HAL_TIM_Base_Start_IT(&htim7);
      }


      } //FINE ZONA SINCRONA

    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */






      if (is_ramping){
    	  divider++;
    	  if (divider > 10){
    		  if(!is_downing){
    			  duty_cycle++;
    			  if(duty_cycle > 240){
    				  is_downing=true;
    			  }
    		  }
    		  else {
    			  duty_cycle = duty_cycle -1;
    			  if(duty_cycle<31){
    				  is_downing=false;
    			  }
    		  }
    	  }
    	  if(duty_cycle>135){
    		  motor_Start(duty_cycle-135,1);
    	  }
    	  else{
        	  motor_Start(135-duty_cycle,0);
    	  }
      }

  }
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Configure the main internal regulator output voltage
  */
  if (HAL_PWREx_ControlVoltageScaling(PWR_REGULATOR_VOLTAGE_SCALE1) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_MSI;
  RCC_OscInitStruct.MSIState = RCC_MSI_ON;
  RCC_OscInitStruct.MSICalibrationValue = 0;
  RCC_OscInitStruct.MSIClockRange = RCC_MSIRANGE_11;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_NONE;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_MSI;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV2;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_2) != HAL_OK)
  {
    Error_Handler();
  }
}

/**
  * @brief I2C1 Initialization Function
  * @param None
  * @retval None
  */
static void MX_I2C1_Init(void)
{

  /* USER CODE BEGIN I2C1_Init 0 */

  /* USER CODE END I2C1_Init 0 */

  /* USER CODE BEGIN I2C1_Init 1 */

  /* USER CODE END I2C1_Init 1 */
  hi2c1.Instance = I2C1;
  hi2c1.Init.Timing = 0x00805C87;
  hi2c1.Init.OwnAddress1 = 0;
  hi2c1.Init.AddressingMode = I2C_ADDRESSINGMODE_7BIT;
  hi2c1.Init.DualAddressMode = I2C_DUALADDRESS_DISABLE;
  hi2c1.Init.OwnAddress2 = 0;
  hi2c1.Init.OwnAddress2Masks = I2C_OA2_NOMASK;
  hi2c1.Init.GeneralCallMode = I2C_GENERALCALL_DISABLE;
  hi2c1.Init.NoStretchMode = I2C_NOSTRETCH_DISABLE;
  if (HAL_I2C_Init(&hi2c1) != HAL_OK)
  {
    Error_Handler();
  }

  /** Configure Analogue filter
  */
  if (HAL_I2CEx_ConfigAnalogFilter(&hi2c1, I2C_ANALOGFILTER_ENABLE) != HAL_OK)
  {
    Error_Handler();
  }

  /** Configure Digital filter
  */
  if (HAL_I2CEx_ConfigDigitalFilter(&hi2c1, 0) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN I2C1_Init 2 */

  /* USER CODE END I2C1_Init 2 */

}

/**
  * @brief TIM1 Initialization Function
  * @param None
  * @retval None
  */
static void MX_TIM1_Init(void)
{

  /* USER CODE BEGIN TIM1_Init 0 */

  /* USER CODE END TIM1_Init 0 */

  TIM_MasterConfigTypeDef sMasterConfig = {0};
  TIM_OC_InitTypeDef sConfigOC = {0};
  TIM_BreakDeadTimeConfigTypeDef sBreakDeadTimeConfig = {0};

  /* USER CODE BEGIN TIM1_Init 1 */

  /* USER CODE END TIM1_Init 1 */
  htim1.Instance = TIM1;
  htim1.Init.Prescaler = 13;
  htim1.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim1.Init.Period = 255;
  htim1.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  htim1.Init.RepetitionCounter = 0;
  htim1.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
  if (HAL_TIM_PWM_Init(&htim1) != HAL_OK)
  {
    Error_Handler();
  }
  sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET;
  sMasterConfig.MasterOutputTrigger2 = TIM_TRGO2_RESET;
  sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
  if (HAL_TIMEx_MasterConfigSynchronization(&htim1, &sMasterConfig) != HAL_OK)
  {
    Error_Handler();
  }
  sConfigOC.OCMode = TIM_OCMODE_PWM1;
  sConfigOC.Pulse = 0;
  sConfigOC.OCPolarity = TIM_OCPOLARITY_HIGH;
  sConfigOC.OCFastMode = TIM_OCFAST_DISABLE;
  sConfigOC.OCIdleState = TIM_OCIDLESTATE_RESET;
  sConfigOC.OCNIdleState = TIM_OCNIDLESTATE_RESET;
  if (HAL_TIM_PWM_ConfigChannel(&htim1, &sConfigOC, TIM_CHANNEL_4) != HAL_OK)
  {
    Error_Handler();
  }
  sBreakDeadTimeConfig.OffStateRunMode = TIM_OSSR_DISABLE;
  sBreakDeadTimeConfig.OffStateIDLEMode = TIM_OSSI_DISABLE;
  sBreakDeadTimeConfig.LockLevel = TIM_LOCKLEVEL_OFF;
  sBreakDeadTimeConfig.DeadTime = 0;
  sBreakDeadTimeConfig.BreakState = TIM_BREAK_DISABLE;
  sBreakDeadTimeConfig.BreakPolarity = TIM_BREAKPOLARITY_HIGH;
  sBreakDeadTimeConfig.BreakFilter = 0;
  sBreakDeadTimeConfig.Break2State = TIM_BREAK2_DISABLE;
  sBreakDeadTimeConfig.Break2Polarity = TIM_BREAK2POLARITY_HIGH;
  sBreakDeadTimeConfig.Break2Filter = 0;
  sBreakDeadTimeConfig.AutomaticOutput = TIM_AUTOMATICOUTPUT_DISABLE;
  if (HAL_TIMEx_ConfigBreakDeadTime(&htim1, &sBreakDeadTimeConfig) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN TIM1_Init 2 */

  /* USER CODE END TIM1_Init 2 */
  HAL_TIM_MspPostInit(&htim1);

}

/**
  * @brief TIM6 Initialization Function
  * @param None
  * @retval None
  */
static void MX_TIM6_Init(void)
{

  /* USER CODE BEGIN TIM6_Init 0 */

  /* USER CODE END TIM6_Init 0 */

  TIM_MasterConfigTypeDef sMasterConfig = {0};

  /* USER CODE BEGIN TIM6_Init 1 */

  /* USER CODE END TIM6_Init 1 */
  htim6.Instance = TIM6;
  htim6.Init.Prescaler = 479;
  htim6.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim6.Init.Period = 1999;
  htim6.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
  if (HAL_TIM_Base_Init(&htim6) != HAL_OK)
  {
    Error_Handler();
  }
  sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET;
  sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
  if (HAL_TIMEx_MasterConfigSynchronization(&htim6, &sMasterConfig) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN TIM6_Init 2 */

  /* USER CODE END TIM6_Init 2 */

}

/**
  * @brief TIM7 Initialization Function
  * @param None
  * @retval None
  */
static void MX_TIM7_Init(void)
{

  /* USER CODE BEGIN TIM7_Init 0 */

  /* USER CODE END TIM7_Init 0 */

  TIM_MasterConfigTypeDef sMasterConfig = {0};

  /* USER CODE BEGIN TIM7_Init 1 */

  /* USER CODE END TIM7_Init 1 */
  htim7.Instance = TIM7;
  htim7.Init.Prescaler = 47;
  htim7.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim7.Init.Period = 8332;
  htim7.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
  if (HAL_TIM_Base_Init(&htim7) != HAL_OK)
  {
    Error_Handler();
  }
  sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET;
  sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
  if (HAL_TIMEx_MasterConfigSynchronization(&htim7, &sMasterConfig) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN TIM7_Init 2 */

  /* USER CODE END TIM7_Init 2 */

}

/**
  * @brief USART1 Initialization Function
  * @param None
  * @retval None
  */
static void MX_USART1_UART_Init(void)
{

  /* USER CODE BEGIN USART1_Init 0 */

  /* USER CODE END USART1_Init 0 */

  /* USER CODE BEGIN USART1_Init 1 */

  /* USER CODE END USART1_Init 1 */
  huart1.Instance = USART1;
  huart1.Init.BaudRate = 57600;
  huart1.Init.WordLength = UART_WORDLENGTH_8B;
  huart1.Init.StopBits = UART_STOPBITS_1;
  huart1.Init.Parity = UART_PARITY_NONE;
  huart1.Init.Mode = UART_MODE_TX_RX;
  huart1.Init.HwFlowCtl = UART_HWCONTROL_NONE;
  huart1.Init.OverSampling = UART_OVERSAMPLING_16;
  huart1.Init.OneBitSampling = UART_ONE_BIT_SAMPLE_DISABLE;
  huart1.AdvancedInit.AdvFeatureInit = UART_ADVFEATURE_NO_INIT;
  if (HAL_UART_Init(&huart1) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN USART1_Init 2 */

  /* USER CODE END USART1_Init 2 */

}

/**
  * @brief USART2 Initialization Function
  * @param None
  * @retval None
  */
static void MX_USART2_UART_Init(void)
{

  /* USER CODE BEGIN USART2_Init 0 */

  /* USER CODE END USART2_Init 0 */

  /* USER CODE BEGIN USART2_Init 1 */

  /* USER CODE END USART2_Init 1 */
  huart2.Instance = USART2;
  huart2.Init.BaudRate = 115200;
  huart2.Init.WordLength = UART_WORDLENGTH_8B;
  huart2.Init.StopBits = UART_STOPBITS_1;
  huart2.Init.Parity = UART_PARITY_NONE;
  huart2.Init.Mode = UART_MODE_TX_RX;
  huart2.Init.HwFlowCtl = UART_HWCONTROL_NONE;
  huart2.Init.OverSampling = UART_OVERSAMPLING_16;
  huart2.Init.OneBitSampling = UART_ONE_BIT_SAMPLE_DISABLE;
  huart2.AdvancedInit.AdvFeatureInit = UART_ADVFEATURE_NO_INIT;
  if (HAL_UART_Init(&huart2) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN USART2_Init 2 */

  /* USER CODE END USART2_Init 2 */

}

/**
  * @brief GPIO Initialization Function
  * @param None
  * @retval None
  */
static void MX_GPIO_Init(void)
{
  GPIO_InitTypeDef GPIO_InitStruct = {0};
  /* USER CODE BEGIN MX_GPIO_Init_1 */

  /* USER CODE END MX_GPIO_Init_1 */

  /* GPIO Ports Clock Enable */
  __HAL_RCC_GPIOA_CLK_ENABLE();
  __HAL_RCC_GPIOB_CLK_ENABLE();

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(GPIOB, Escon_DIR_Pin|Escon_Enable_Pin, GPIO_PIN_RESET);

  /*Configure GPIO pin : MSW2_Pin */
  GPIO_InitStruct.Pin = MSW2_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_IT_RISING;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  HAL_GPIO_Init(MSW2_GPIO_Port, &GPIO_InitStruct);

  /*Configure GPIO pin : PB3 */
  GPIO_InitStruct.Pin = GPIO_PIN_3;
  GPIO_InitStruct.Mode = GPIO_MODE_IT_RISING;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);

  /*Configure GPIO pins : Escon_DIR_Pin Escon_Enable_Pin */
  GPIO_InitStruct.Pin = Escon_DIR_Pin|Escon_Enable_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);

  /* EXTI interrupt init*/
  HAL_NVIC_SetPriority(EXTI3_IRQn, 0, 0);
  HAL_NVIC_EnableIRQ(EXTI3_IRQn);

  HAL_NVIC_SetPriority(EXTI9_5_IRQn, 0, 0);
  HAL_NVIC_EnableIRQ(EXTI9_5_IRQn);

  /* USER CODE BEGIN MX_GPIO_Init_2 */

  /* USER CODE END MX_GPIO_Init_2 */
}

/* USER CODE BEGIN 4 */
// Questa funzione viene chiamata automaticamente dalla HAL quando scatta un interrupt EXTI
void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
    // Controlliamo se l'interrupt è stato generato dal pin 3 (PB3) o dal pin 8 (PA8)
    if(GPIO_Pin == GPIO_PIN_3 || GPIO_Pin == GPIO_PIN_8)
    {
        // Ferma immediatamente il motore
        motor_Stop();
        is_ramping=false;

        // Opzionale: invia un messaggio di notifica (usiamo un timeout bassissimo
        // per non bloccare troppo a lungo l'esecuzione dentro l'interrupt)
        char msg_stop[] = "EMERGENZA: Microswitch premuto. Motore fermato!\r\n";
        HAL_UART_Transmit(&huart1, (uint8_t*)msg_stop, strlen(msg_stop), 10);
    }
}

void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
{
    if (htim->Instance == TIM7)
    {
    	allowed_tick = true;
        // questo gira a 100 Hz
    }
}
/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
