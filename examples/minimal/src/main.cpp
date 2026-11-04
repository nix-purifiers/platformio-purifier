#include <Arduino.h>
#include <ArduinoJson.h>
#include <Adafruit_GFX.h>
void setup() {
  JsonDocument doc;
  GFXcanvas1 canvas(8,8);
  canvas.drawPixel(1,1,1);
  doc["answer"] = 42;
  doc["pixel"] = canvas.getPixel(1,1);
  Serial.begin(9600);
  serializeJson(doc, Serial);
}
void loop() {}
