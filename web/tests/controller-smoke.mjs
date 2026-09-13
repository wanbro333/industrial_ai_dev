// Public MQTT integration using the production Python runtime and production C# device model.
// Does not claim to test Unity rendering or WebGL; that needs a licensed Unity build.
import mqtt from 'mqtt';
import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import { once } from 'node:events';
import { mkdir, writeFile } from 'node:fs/promises';
import crypto from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Protocol } from '../src/protocol.js';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const session=crypto.randomBytes(8).toString('hex'), protocol=new Protocol(session);
const prefix=`brics2026/${session}/cell01/`;
const python=spawn(path.join(root,'.venv/Scripts/python.exe'),['-u','-m','controller.main','--session',session],{cwd:root,stdio:['ignore','pipe','pipe']});
let pythonLog='';
python.stderr.on('data',data=>{pythonLog+=data.toString();});
const device=spawn('dotnet',[path.join(root,'tests/device_harness/bin/Release/net8.0/DeviceHarness.dll')],{stdio:['pipe','pipe','pipe']});
device.stderr.on('data',data=>process.stderr.write(data));
const lines=createInterface({input:device.stdout});
let pendingOutput=null,output=null,inputs=null,started=false,round=0,previousStep='',commandCount=0,authorize='';
const client=mqtt.connect('wss://broker.emqx.io:8084/mqtt',{clientId:`sim-${protocol.peer}`,clean:true,reconnectPeriod:0,connectTimeout:10000});
const begin=performance.now();
function publish(stream,data){const msg=protocol.make(data);client.publish(prefix+stream,JSON.stringify(msg),{qos:1,retain:false});return msg.id;}
client.on('message',(topic,body,packet)=>{
  const msg=protocol.accept(body.toString(),packet.retain);
  if(msg){pendingOutput=msg.data;output=msg.data;commandCount++;}
});
let result;
try {
  await Promise.race([once(client,'connect'),new Promise((_,reject)=>setTimeout(()=>reject(new Error('WSS timeout')),15000))]);
  await client.subscribeAsync(prefix+'control/outputs',{qos:1});
  while(performance.now()-begin<240000){
    const request={dt:.05,t:(performance.now()-begin)/1000};
    if(pendingOutput){request.outputs=pendingOutput;pendingOutput=null;}
    if(authorize){request.authorize=authorize;authorize='';}
    const response=once(lines,'line');
    device.stdin.write(JSON.stringify(request)+'\n');
    const [line]=await response,r=JSON.parse(line);
    protocol.epoch=r.epoch;inputs=r.inputs;
    if(round++%4===0)publish('device/inputs',inputs);
    if(!started&&output?.ready){authorize=publish('ui/events',{action:'start'});started=true;console.log('START through public MQTT');}
    if(output?.step!==previousStep){previousStep=output?.step;console.log(`Status=${output?.status} step=${previousStep}`);}
    if(output?.fault&&started)throw new Error(output.fault);
    if(inputs.ok_count>=1&&inputs.bin1_count>=2&&inputs.bin2_count>=1){
      publish('ui/events',{action:'stop'});
      result={passed:true,session,elapsed_seconds:Math.round((performance.now()-begin)/1000),received_commands:commandCount,
        counts:{ok:inputs.ok_count,bin1:inputs.bin1_count,bin2:inputs.bin2_count},
        path:'Python production runtime / EMQX TCP+WSS / MQTT.js protocol / production C# device model; no Unity rendering'};
      break;
    }
    await new Promise(resolve=>setTimeout(resolve,50));
  }
  if(!result)throw new Error('Full cycle timeout: '+JSON.stringify({output,inputs}));
  console.log(JSON.stringify(result));
} finally {
  client.end(true);python.kill();device.stdin.end();lines.close();
  await mkdir(path.join(root,'artifacts'),{recursive:true});
  await writeFile(path.join(root,'artifacts/controller-mqtt.log'),pythonLog);
  if(result)await writeFile(path.join(root,'artifacts/controller-mqtt.json'),JSON.stringify(result,null,2));
}
