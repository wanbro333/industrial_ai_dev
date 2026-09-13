// Real Unity WebGL + DOM controls + public EMQX + production Python runtime.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import crypto from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import mqtt from 'mqtt';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
process.env.PLAYWRIGHT_BROWSERS_PATH ||= path.join(root,'.cache/playwright');
const { chromium } = await import('@playwright/test');
const artifacts=path.join(root,'artifacts');await mkdir(artifacts,{recursive:true});
const lifecycleOnly=process.env.CELL_LIFECYCLE_ONLY==='1';
const reportName=lifecycleOnly?'webgl-lifecycle':'webgl-acceptance';
const session=crypto.randomBytes(8).toString('hex'),port=8766;
const observed=[];
const observer=mqtt.connect('mqtt://broker.emqx.io:1883',{clientId:'observe-'+session,clean:true});
observer.on('connect',()=>observer.subscribe(`brics2026/${session}/cell01/ui/events`,{qos:1}));
observer.on('message',(topic,body)=>{observed.push(body.toString());});
const python=path.join(root,'.venv/Scripts/python.exe');
let controllerLog='',serverLog='';
let controller;
function startController(){
  controller=spawn(python,['-u','-m','controller.main','--session',session,'--web-port',String(port)],{cwd:root,stdio:['ignore','pipe','pipe']});
  controller.stderr.on('data',d=>{controllerLog+=d.toString();});return controller;
}
startController();
const server=spawn(python,['-u','scripts/serve.py','--port',String(port)],{cwd:root,stdio:['ignore','pipe','pipe']});
server.stderr.on('data',d=>{serverLog+=d.toString();});
process.on('exit',()=>{controller?.kill();server.kill();observer.end(true);});
const browser=await chromium.launch({channel:process.env.CELL_BROWSER||'chromium',headless:true,args:['--enable-webgl','--ignore-gpu-blocklist','--enable-unsafe-swiftshader']});
const context=await browser.newContext({viewport:{width:1500,height:1050},deviceScaleFactor:1});
const page=await context.newPage();
const errors=[],messages=[],checks=[];
const frames=[];
page.on('websocket',socket=>socket.on('framesent',event=>{
  const body=Buffer.isBuffer(event.payload)?event.payload:Buffer.from(event.payload);
  if(body.includes(Buffer.from('ui/events')))frames.push(body.toString('hex'));
}));
page.on('pageerror',e=>errors.push(e.message));
page.on('console',m=>{if(m.type()==='error')errors.push(m.text());messages.push(m.text());});
const state=()=>page.evaluate(()=>({inputs:window.cellBridge?.inputs,outputs:window.cellBridge?.outputs,
  lastUiEvent:window.cellBridge?.lastUiEvent,lastUiAction:window.cellBridge?.lastUiAction,uiPackets:window.uiPackets}));
const check=(name)=>{checks.push(name);console.log('PASS '+name);};
const wait=async(fn,timeout=20000)=>page.waitForFunction(fn,null,{timeout});
try {
  await page.goto(`http://127.0.0.1:${port}/?session=${session}`,{waitUntil:'domcontentloaded'});
  await wait(()=>window.cellBridge?.unity&&window.cellBridge?.outputs?.ready,90000);
  await page.evaluate(()=>{window.uiPackets=[];window.cellBridge.client.on('packetsend',p=>{
    if(p.cmd==='publish'&&p.topic.endsWith('/ui/events'))window.uiPackets.push({topic:p.topic,payload:String(p.payload),id:p.messageId});
  });window.uiAcks=[];window.cellBridge.client.on('packetreceive',p=>{if(p.cmd==='puback')window.uiAcks.push(p.messageId);});});
  assert.equal(await page.locator('#loading').isHidden(),true);
  check('Unity WebGL loads and Python handshake reaches ready');
  await page.screenshot({path:path.join(artifacts,'webgl-idle.png'),fullPage:true});
  if(process.env.CELL_VISUAL_ONLY==='1'){console.log('Visual probe complete');}
  else if(lifecycleOnly){
    await page.locator('#auto-feed').uncheck();
    await wait(()=>window.cellBridge.outputs.auto_feed===false);
    await page.locator('#feed').click();await wait(()=>window.cellBridge.outputs.queued===1);
    await page.locator('#start').click();
    await wait(()=>window.cellBridge.inputs.carrier_x>-3.2);
    const cdp=await context.newCDPSession(page);
    await cdp.send('Debugger.enable');
    await cdp.send('Debugger.pause');
    await new Promise(resolve=>setTimeout(resolve,3500));
    await cdp.send('Debugger.resume');
    await cdp.send('Debugger.disable');
    await wait(()=>window.cellBridge.inputs.visible&&window.cellBridge.inputs.communication_hold&&window.cellBridge.outputs.status===2);
    const frozen=(await state()).inputs.carrier_x;
    await page.waitForTimeout(1200);assert.equal((await state()).inputs.carrier_x,frozen);
    check('Actual browser execution suspension/resumption holds position and requires a new start');
    await page.locator('#start').click();
    await page.waitForFunction(x=>window.cellBridge.inputs.carrier_x>x+.1,frozen);
    await page.evaluate(()=>window.cellBridge.client.end(true));
    await wait(()=>!window.cellBridge.connected&&window.cellBridge.inputs.communication_hold);
    const disconnected=(await state()).inputs.carrier_x;
    await page.waitForTimeout(3500);assert.equal((await state()).inputs.carrier_x,disconnected);
    await page.evaluate(()=>window.cellBridge.client.reconnect());
    await wait(()=>window.cellBridge.connected&&window.cellBridge.outputs.status===2);
    await page.waitForTimeout(1200);assert.equal((await state()).inputs.carrier_x,disconnected);
    check('Actual WSS disconnect/reconnect holds the workpiece without automatic resumption');
    await page.locator('#start').click();
    await page.waitForFunction(x=>window.cellBridge.inputs.carrier_x>x+.1,disconnected);
    check('Explicit start resumes after connection recovery');
  }
  else {
    await page.locator('#auto-feed').uncheck();
    await wait(()=>window.cellBridge.outputs.auto_feed===false);
    await page.locator('#recipe').selectOption('blue_forward');
    await page.locator('#feed').click();
    await wait(()=>window.cellBridge.outputs.queued===1);
    await page.locator('#start').click();
    await wait(()=>window.cellBridge.inputs.carrier_present&&window.cellBridge.inputs.carrier_x>-3.4);
    await page.locator('#stop').click();
    await wait(()=>window.cellBridge.outputs.status===2);
    const paused=(await state()).inputs.carrier_x;
    await page.waitForTimeout(1200);
    assert.equal((await state()).inputs.carrier_x,paused);
    check('Pause freezes actual conveyor position');
    await page.locator('#start').click();
    await wait(()=>window.cellBridge.inputs.ok_count===1,25000);
    await wait(()=>window.cellBridge.outputs.step==='WAIT_CARRIER');
    check('Blue forward is released once');
    await page.locator('#manual').click();
    await wait(()=>window.cellBridge.outputs.status===2&&!window.cellBridge.inputs.automatic);
    assert.equal(await page.locator('#start').isDisabled(),true);
    await page.locator('#automatic').click();
    await wait(()=>window.cellBridge.inputs.automatic);
    assert.equal((await state()).outputs.status,2);
    await page.locator('#start').click();
    check('Manual selector pauses; automatic selector alone does not resume');
    for(const [recipe,key,count] of [['yellow_forward','bin1_count',1],['blue_reverse','bin2_count',1],['yellow_reverse','bin1_count',2],['empty','empty_count',1]]){
      await page.locator('#recipe').selectOption(recipe);await page.locator('#feed').click();
      await page.waitForFunction(({key,count})=>window.cellBridge.inputs[key]===count,{key,count},{timeout:45000});
      await wait(()=>window.cellBridge.outputs.step==='WAIT_CARRIER',30000);
      check(`${recipe} reaches expected physical destination`);
    }
    await page.screenshot({path:path.join(artifacts,'webgl-sorted.png'),fullPage:true});
    await page.locator('#recipe').selectOption('yellow_reverse');await page.locator('#feed').click();
    await wait(()=>window.cellBridge.inputs.holding,20000);
    await page.locator('[data-camera="sorting"]').click();
    await page.screenshot({path:path.join(artifacts,'webgl-gripping.png'),fullPage:true});
    await page.locator('#estop').click();
    await wait(()=>window.cellBridge.inputs.estop&&!window.cellBridge.inputs.holding&&!window.cellBridge.inputs.carrier_present);
    await wait(()=>window.cellBridge.outputs?.status===3);
    await page.screenshot({path:path.join(artifacts,'webgl-estop.png'),fullPage:true});
    check('Emergency stop clears a held workpiece and carrier locally');
    await page.locator('#release').click();
    await wait(()=>window.cellBridge.outputs?.status===0&&window.cellBridge.outputs?.ready);
    await page.waitForTimeout(1200);
    assert.equal((await state()).inputs.carrier_present,false);
    check('Emergency release homes and remains idle');
    // Actual connection loss: kill controller, observe watchdog, restart with in-process material.
    await page.locator('#recipe').selectOption('blue_reverse');await page.locator('#feed').click();
    await page.locator('#start').click();
    await wait(()=>window.cellBridge.inputs.carrier_present);
    controller.kill();
    await wait(()=>window.cellBridge.inputs.communication_hold,8000);
    const held=(await state()).inputs.carrier_x;await page.waitForTimeout(1000);
    assert.equal((await state()).inputs.carrier_x,held);
    startController();
    await wait(()=>window.cellBridge.outputs?.fault==='RECOVERY_RESET_REQUIRED',15000);
    check('Controller loss freezes equipment; restart with workpiece requires reset');
    await page.locator('#reset').click();
    await wait(()=>window.cellBridge.outputs?.status===0&&window.cellBridge.outputs?.ready);
    assert.equal((await state()).inputs.carrier_present,false);
    await page.reload({waitUntil:'domcontentloaded'});
    await wait(()=>window.cellBridge?.unity&&window.cellBridge.outputs?.ready,60000);
    assert.equal((await state()).outputs.status,0);
    check('Browser refresh creates a new epoch without automatic start');
  }
  assert.deepEqual(errors,[],'Browser runtime errors');
  check('No browser runtime errors');
  await writeFile(path.join(artifacts,reportName+'.json'),JSON.stringify({passed:true,session,checks,state:await state()},null,2));
} catch(error){
  await page.screenshot({path:path.join(artifacts,'webgl-failure.png'),fullPage:true}).catch(()=>{});
  await writeFile(path.join(artifacts,reportName+'.json'),JSON.stringify({passed:false,error:String(error),errors,checks,state:await state().catch(()=>null)},null,2));
  throw error;
} finally {
  await writeFile(path.join(artifacts,'webgl-browser.log'),messages.join('\n'));
  await writeFile(path.join(artifacts,'webgl-controller.log'),controllerLog);
  await writeFile(path.join(artifacts,'webgl-server.log'),serverLog);
  await writeFile(path.join(artifacts,'webgl-wire.log'),observed.join('\n'));
  await writeFile(path.join(artifacts,'webgl-frames.json'),JSON.stringify({frames,acks:await page.evaluate(()=>window.uiAcks).catch(()=>[])},null,2));
  observer.end(true);
  await browser.close();controller.kill();server.kill();
}
