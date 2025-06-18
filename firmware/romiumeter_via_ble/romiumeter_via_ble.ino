
/*
  Edited on 05/11/2024 by Diwakar Reddy BK.
  This Arduino code configures a BLE device that transmits IMU data, including
  raw gyro readings, over BLE using a custom service and characteristic. The
  gyro data is converted from integer format to bytes and includes a timestamp
  in microseconds. The LED color indicates the connection status: red when a
  central device is connected, off otherwise.
*/

#include <ArduinoBLE.h>
#include "Wire.h"
#include "variable.h"

#define deviceServiceUuid  "7271f06e-5088-46c9-ab77-4e246b3ea3cb" // UUID for BLE service
#define deviceServiceimudataCharacteristicUuid  "660c4a6f-16d8-4e57-8fdb-a4058934242d" // UUID for BLE characteristic

// Union to convert a 16-bit integer to two bytes
union IntToBytes {
    uint16_t integer;
    struct {
        uint8_t byte1;
        uint8_t byte2;
    } bytes;
};

// Converts an array of 16-bit integers to bytes and stores in a byte array
void convertIntegersToBytes(const uint16_t* integers, size_t length, uint8_t* bytes){
  for (size_t i = 0; i < length; i++){
    IntToBytes converter;
    converter.integer = integers[i];
    bytes[2 * i] = converter.bytes.byte1;
    bytes[2 * i + 1] = converter.bytes.byte2;
  }
}

// BLE Service and Characteristic definitions
BLEService imudataService(deviceServiceUuid);
BLECharacteristic imudata(deviceServiceimudataCharacteristicUuid, BLEWrite | BLERead | BLENotify, 24);

// Function to turn on only the red LED, indicating BLE connection
void rgbLedRed() {
  digitalWrite(LEDG, HIGH);  // green LED off
  digitalWrite(LEDB, LOW);  // blue LED off
  digitalWrite(LEDR, LOW);   // red LED on
}

// Function to turn off all LEDs
void rgbLedoff() {
  digitalWrite(LEDG, HIGH);  // green LED off
  digitalWrite(LEDB, HIGH);  // blue LED off
  digitalWrite(LEDR, HIGH);  // red LED off
}

void setup(){
  Wire.begin();
  mpu1.begin(1,0);  // Initialize IMU sensor
  BLE.begin();
  BLE.setAdvertisedService(imudataService);  // Set the advertised BLE service
  imudataService.addCharacteristic(imudata); // Add characteristic to the service
  BLE.addService(imudataService);            // Add service to BLE
  BLE.setLocalName("romiumeter_frozen_shoulder");            // Set BLE device name
  BLE.setDeviceName("romiumeter_frozen_shoulder");
  BLE.setConnectionInterval(0x0006, 0x0006); // Set BLE connection interval for faster updates
  BLE.advertise();                           // Start advertising the BLE service
}

void loop() {
  BLEDevice central = BLE.central(); // Check for BLE central device
  if ( central.connected() )         // If a central device is connected
  { 
    rgbLedRed();                     // Indicate connection with red LED
    mpu1.update();                   // Update IMU sensor data

    unsigned long value = micros();  // Get timestamp in microseconds
    uint16_t integers[] = {mpu1.getrawGyroX(), mpu1.getrawGyroY(), mpu1.getrawGyroZ()}; // Get gyro data
    size_t numIntegers = sizeof(integers) / sizeof(integers[0]); // Calculate number of integers

    // Array to hold the combined bytes (gyro data + timestamp)
    byte combinedBytes[sizeof(integers) + sizeof(unsigned long)];
    uint8_t bytes[2*numIntegers];

    convertIntegersToBytes(integers, numIntegers, bytes);  // Convert gyro data to bytes
    memcpy(combinedBytes, bytes, sizeof(integers));        // Copy gyro bytes to combined array
    memcpy(combinedBytes + sizeof(integers), &value, sizeof(unsigned long)); // Copy timestamp to combined array

    imudata.writeValue(combinedBytes, sizeof(combinedBytes)); // Write data to BLE characteristic
  }
  else 
  {
    rgbLedoff(); // Turn off LED if no central device is connected
  }
}
