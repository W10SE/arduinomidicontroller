// Define the analog pins for Joystick 1
const int joy1X = A0;
const int joy1Y = A1;

// Define the analog pins for Joystick 2
const int joy2X = A2;
const int joy2Y = A3;

// Define the analog pins for Joystick 3
const int joy3X = A4;
const int joy3Y = A5;

// Variables to store the readings
int val1X, val1Y;
int val2X, val2Y;
int val3X, val3Y;

void setup() {
  // Initialize serial communication at 9600 bits per second
  Serial.begin(9600);
}

void loop() {
  // Read values from Joystick 1
  val1X = analogRead(joy1X);
  val1Y = analogRead(joy1Y);

  // Read values from Joystick 2
  val2X = analogRead(joy2X);
  val2Y = analogRead(joy2Y);

  // Read values from Joystick 3
  val3X = analogRead(joy3X);
  val3Y = analogRead(joy3Y);

  // Print the results to the Serial Monitor
  Serial.print("Joy1: X="); 
  Serial.print(val1X); 
  Serial.print(" Y="); 
  Serial.print(val1Y); 
  Serial.print("  |  ");

  Serial.print("Joy2: X="); 
  Serial.print(val2X); 
  Serial.print(" Y="); 
  Serial.print(val2Y); 
  Serial.print("  |  ");

  Serial.print("Joy3: X="); 
  Serial.print(val3X); 
  Serial.print(" Y="); 
  Serial.println(val3Y); // println adds a new line at the end

  // Small delay to make the Serial Monitor readable
  delay(100); 
}