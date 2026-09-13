import { CellBridge } from './bridge.js';

const $ = id => document.getElementById(id);
const steps = { HOME:'初始化', WAIT_CARRIER:'等待载具', DETECT:'输送与检测', APPROACH:'挡停定位', LIFT:'顶升物料',
  PICK_DOWN:'下降取料', GRIP:'夹取确认', PICK_UP:'抬起物料', TRAVEL:'平移至料仓', DROP_DOWN:'下降放料',
  UNGRIP:'松爪确认', DROP_UP:'抬起夹爪', RETURN:'返回原位', LOWER:'顶升缩回', RELEASE:'载具放行', RESET_STOP:'挡停复位' };
const statuses = ['闲置中','自动运行中','暂停中','急停中'];
const statusClasses = ['idle','running','paused','estop'];
const signals = { divider_carrier:'分隔位载具', detect_carrier:'检测位载具', detect_material:'检测位有料', stop_carrier:'挡停位载具', stop_material:'挡停位有料',
  color_yellow:'颜色 / 黄色', direction_reverse:'方向 / 反向', holding:'夹持有料',
  divider:'分隔气缸', stopper:'挡停气缸', lift:'顶升气缸', axis1:'平移气缸 1', axis2:'平移气缸 2', hoist:'搬运升降', grip:'夹爪闭合' };
for (const [key,label] of Object.entries(signals)) {
  const div = document.createElement('div'); div.className = 'signal'; div.id = 'signal-' + key;
  const dot = document.createElement('i'), title = document.createElement('span'), value = document.createElement('b');
  title.textContent = label; value.textContent = '—'; div.append(dot,title,value); $('signals').append(div);
}
let previousStep = '', previousStatus = -1;
const view = {
  session(session) { $('session').textContent = session; },
  log(message) {
    const li = document.createElement('li'), time = document.createElement('time'), text = document.createElement('span');
    time.textContent = new Date().toLocaleTimeString('zh-CN',{hour12:false}); text.textContent = message;
    li.append(time,text); $('event-log').prepend(li);
    while ($('event-log').children.length > 30) $('event-log').lastElementChild.remove();
  },
  render(bridge) {
    const i = bridge.inputs, o = bridge.outputs || {};
    if (!i) return;
    const fresh = bridge.connected && performance.now() - bridge.controllerAt < 3000;
    const status = i.estop ? 3 : (i.communication_hold && o.status === 1) ? 2 : o.status ?? 0;
    $('network').textContent = !bridge.connected ? 'MQTT 连接中' : fresh ? '控制器已同步' : '等待 Python 控制器';
    $('network-dot').classList.toggle('online', fresh);
    $('status-code').textContent = `Status = ${status}`; $('status-name').textContent = statuses[status];
    if (previousStatus !== status) { $('status-lamp').className = `state-lamp ${statusClasses[status]}`; previousStatus = status; this.log(statuses[status]); }
    $('ready').textContent = i.estop ? '已锁定' : o.fault || i.device_fault ? '故障' : o.ready ? '已就绪' : '初始化';
    $('state-note').textContent = i.estop ? '现场已停止并清料。释放急停后重新初始化。' : i.device_fault || o.fault ||
      (!fresh ? '等待 Python 控制器连接，恢复后请重新启动。' : o.note || '等待初始化反馈');
    $('automatic').classList.toggle('selected', i.automatic); $('manual').classList.toggle('selected', !i.automatic);
    $('start').disabled = !fresh || !o.ready || !i.automatic || status === 1 || status === 3 || !!o.fault;
    $('stop').disabled = status !== 1; $('estop').disabled = status === 3;
    $('reset').disabled = !fresh || (o.status !== 0 && o.status !== 2) || i.estop;
    $('clear-counts').disabled = status !== 0;
    $('release').hidden = !i.estop;
    $('feed').disabled = !fresh || status === 3;
    if (typeof o.auto_feed === 'boolean') $('auto-feed').checked = o.auto_feed;
    $('queued').textContent = o.queued || 0;
    $('ok-count').textContent = i.ok_count; $('bin1-count').textContent = i.bin1_count; $('bin2-count').textContent = i.bin2_count;
    $('step-name').textContent = steps[o.step] || '等待连接';
    $('step-detail').textContent = o.step ? `${o.step} · ${(o.step_elapsed || 0).toFixed(1)} s` : '输入、输出与实际动作闭环';
    if (previousStep !== o.step && o.step) { previousStep = o.step; this.log(steps[o.step] || o.step); }
    for (const key of Object.keys(signals)) {
      const div = $('signal-' + key), value = i[key];
      div.classList.toggle('active', value > .5 || value === true);
      div.lastChild.textContent = typeof value === 'boolean' ? (value ? '1' : '0') : `${Math.round(value * 100)}%`;
    }
    $('packet-stats').textContent = `发送 ${bridge.sent} · 接收 ${bridge.received} · 拒绝 ${bridge.rejected}`;
    $('latency').textContent = fresh ? `控制消息距今 ${Math.round(performance.now() - bridge.controllerAt)} ms` : '仅虚拟设备数据';
  }
};

window.cellBridge = new CellBridge(view);
const bridge = window.cellBridge;
for (const action of ['start','stop','reset','estop','release']) $(action).addEventListener('click', () => bridge.act(action));
$('automatic').onclick = () => bridge.act('mode',true);
$('manual').onclick = () => bridge.act('mode',false);
$('clear-counts').onclick = () => bridge.act('clear_counts');
$('auto-feed').onchange = event => bridge.act('auto_feed',event.target.checked);
$('feed').onclick = () => bridge.act('feed',false,$('recipe').value);
$('jam').onchange = event => bridge.act('jam',false,event.target.value);
$('session-copy').onclick = async () => { try { await navigator.clipboard.writeText(bridge.protocol.session); view.log('会话编号已复制'); } catch { view.log('会话编号显示在右上角，可手动复制'); } };
document.querySelectorAll('[data-camera]').forEach(button => button.onclick = () => {
  document.querySelectorAll('[data-camera]').forEach(b => b.classList.toggle('selected', b === button));
  bridge.act('camera',false,button.dataset.camera);
});
setInterval(() => view.render(bridge),250);

async function loadUnity() {
  const config = window.UNITY_CONFIG;
  if (!config || config.loaderUrl.includes('{{{')) throw new Error('尚未生成 Unity WebGL 构建。请运行 scripts/build-webgl.ps1。');
  await new Promise((resolve,reject) => { const script = document.createElement('script'); script.src = config.loaderUrl; script.onload = resolve;
    script.onerror = () => reject(new Error('Unity 加载器不存在，请检查 WebGL 构建目录。')); document.body.append(script); });
  const instance = await window.createUnityInstance($('unity-canvas'), { ...config, devicePixelRatio:Math.min(devicePixelRatio,1.5) }, progress => { $('load-progress').value = progress; });
  bridge.setUnity(instance); $('loading').hidden = true; view.log('Unity 场景加载完成');
}
loadUnity().catch(error => { $('load-detail').textContent = error.message; $('load-progress').hidden = true; console.error(error); });
