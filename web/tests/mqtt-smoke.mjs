// Both clients use the user-authorized public broker and an isolated random topic.
// This checks MQTT.js WSS against Paho TCP; no real device topics are touched.
import mqtt from 'mqtt';
import { spawn } from 'node:child_process';
import crypto from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const session = crypto.randomBytes(8).toString('hex');
const topic = `brics2026/${session}/cell01/probe/`;
const python = spawn(path.join(root,'.venv/Scripts/python.exe'),['-u','-c',`
import paho.mqtt.client as mqtt,time
c=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id='probe-py-${session}')
def connect(client,userdata,flags,reason,properties):
 client.subscribe('${topic}request',1)
 print('READY',flush=True)
def receive(client,userdata,msg):
 client.publish('${topic}reply',msg.payload,1,False)
c.on_connect=connect;c.on_message=receive
c.connect('broker.emqx.io',1883,10);c.loop_forever()
`],{stdio:['ignore','pipe','pipe']});
python.stderr.on('data',d=>process.stderr.write(d));
const client = mqtt.connect('wss://broker.emqx.io:8084/mqtt',{clientId:`probe-js-${session}`,clean:true,connectTimeout:10000,reconnectPeriod:0});
try {
  await Promise.race([Promise.all([
    new Promise((resolve,reject)=>{python.stdout.on('data',d=>{if(d.toString().includes('READY'))resolve();});python.on('error',reject);python.on('exit',code=>reject(new Error('Paho exit '+code)));}),
    new Promise((resolve,reject)=>{client.on('connect',resolve);client.on('error',reject);})
  ]),new Promise((_,reject)=>setTimeout(()=>reject(new Error('Broker connection timeout')),20000))]);
  await client.subscribeAsync(topic+'reply',{qos:1});
  const samples=[];
  for(let n=0;n<5;n++){
    const payload=crypto.randomUUID(), start=performance.now();
    const reply=new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>{client.off('message',onMessage);reject(new Error('Round trip timeout'));},5000);
      function onMessage(receivedTopic,body){if(receivedTopic===topic+'reply'&&body.toString()===payload){clearTimeout(timer);client.off('message',onMessage);resolve();}}
      client.on('message',onMessage);
    });
    await client.publishAsync(topic+'request',payload,{qos:1,retain:false});await reply;
    samples.push(Math.round(performance.now()-start));
  }
  console.log(JSON.stringify({broker:'broker.emqx.io',transports:['Paho TCP 1883','MQTT.js WSS 8084'],round_trip_ms:samples,passed:true}));
} finally {client.end(true);python.kill();}
