"""Página da CONVERSA POR VOZ (HTML puro, feita para o celular): GET /voz.

Fluxo: o usuário toca em "Falar" -> o navegador grava (microfone), converte para WAV 16 bits (taxa nativa do microfone, até 48 kHz) -> /voz/transcrever -> texto
-> /chat (o mesmo chat do Sulco, com os dados do município) -> resposta em texto -> /voz/falar (voz da DeepSeek) ou voz do navegador.
No modo "conversa contínua" ele volta a ouvir sozinho quando termina de falar (detecta o fim da sua fala por silêncio).
Todo texto vindo da API entra na página por `textContent` (nunca HTML). O microfone só funciona em HTTPS (ou localhost)."""
from __future__ import annotations

import json

PAGINA = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Sulco: conversa por voz</title>
<style>
:root{--bg:#f6f4ee;--card:#fff;--tx:#1f2a1f;--mut:#667066;--bd:#d9d5c7;--ac:#2f6b3a;--ac2:#e8f1e6;--rec:#b3261e;--warn:#8a5a00;--warnbg:#fff3d6}
@media (prefers-color-scheme:dark){:root{--bg:#161a16;--card:#1f261f;--tx:#e8ece6;--mut:#9aa59a;--bd:#34402f;--ac:#7fc08a;--ac2:#243324;--rec:#ff8a80;--warn:#f0c46a;--warnbg:#3a3014}}
*{box-sizing:border-box}html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--tx);font:17px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;display:flex;flex-direction:column}
header{padding:10px 14px;border-bottom:1px solid var(--bd);background:var(--card)}
h1{font-size:1.05rem;margin:0}small,.mut{color:var(--mut)}
#conf{padding:8px 14px;background:var(--card);border-bottom:1px solid var(--bd);display:none;gap:8px;flex-wrap:wrap}
#conf label{font-size:.78rem;color:var(--mut);display:flex;flex-direction:column;flex:1 1 140px}
select,input[type=text],input[type=password],input[type=number]{font:inherit;padding:8px;border:1px solid var(--bd);border-radius:10px;background:var(--bg);color:var(--tx);width:100%}
#conversa{flex:1;overflow-y:auto;padding:12px 14px}
.msg{margin:10px 0;padding:10px 13px;border-radius:14px;border:1px solid var(--bd);background:var(--card);max-width:92%;white-space:pre-wrap;overflow-wrap:anywhere}
.eu{background:var(--ac2);margin-left:auto}.sist{margin-right:auto}.aviso{background:var(--warnbg);color:var(--warn);font-size:.88rem}
.tag{display:inline-block;font-size:.7rem;color:var(--mut);margin-bottom:4px}
footer{padding:10px 14px calc(10px + env(safe-area-inset-bottom));background:var(--card);border-top:1px solid var(--bd)}
#status{text-align:center;font-size:.9rem;color:var(--mut);min-height:1.4em;margin-bottom:6px}
#linha{display:flex;gap:8px;align-items:center;justify-content:center}
#mic{width:84px;height:84px;border-radius:50%;border:0;background:var(--ac);color:#fff;font-size:.95rem;font-weight:600;cursor:pointer;flex:none}
@media (prefers-color-scheme:dark){#mic{color:#0d1a0d}}
#mic.rec{background:var(--rec);animation:p 1.1s infinite}#mic:disabled{opacity:.55}
@keyframes p{50%{transform:scale(1.07)}}
button.sec{font:inherit;font-size:.85rem;padding:9px 12px;border:1px solid var(--bd);border-radius:10px;background:transparent;color:var(--tx);cursor:pointer}
#digitar{display:flex;gap:6px;margin-top:8px}#digitar input{flex:1}
#chips{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin:6px 0}
#chips button{font:inherit;font-size:.92rem;padding:9px 14px;border-radius:999px;border:1px solid var(--ac);background:var(--ac2);color:var(--tx);cursor:pointer}
#custo{font-size:.72rem;color:var(--mut);text-align:center;margin-top:6px}
#pin{padding:14px;display:none}
</style>
</head>
<body>
<header><h1>Sulco · conversa por voz</h1>
<small>Maíra, assistente automática (não é pessoa nem técnica). Apoia a conversa com o técnico: <b>a avaliar com técnico local</b>.</small></header>

<div id="pin" class="msg aviso">
  <div><b>PIN de acesso</b> (o do arquivo .env do computador):</div>
  <div style="display:flex;gap:8px;margin-top:8px"><input id="pinvalor" type="password" inputmode="numeric" autocomplete="off"><button class="sec" id="pinok">Entrar</button></div>
</div>

<div id="conf">
  <label>Município (opcional)<select id="mun"><option value="">(sem local)</option></select></label>
  <label>Cultura que planta (opcional)<select id="cult"><option value="">(não sei / quero conversar)</option></select></label>
  <label>Ouvir você com<select id="ouvir"><option value="navegador">Navegador (português do Brasil)</option><option value="deepseek">DeepSeek (áudio; detecta o idioma sozinha)</option></select></label>
  <label hidden style="display:none">Voz da resposta<select id="voz"><option value="kokoro">Dora (voz feminina, grátis, feita no servidor)</option><option value="navegador" selected>Navegador (português do Brasil, grátis)</option><option value="deepseek">DeepSeek (paga; NÃO é feita para português)</option><option value="nenhuma">Sem voz (só texto)</option></select></label>
  <label hidden style="display:none">Qual voz (português)<select id="vozbr"><option value="">(automática)</option></select></label>
  <label hidden style="display:none">Velocidade da fala<select id="vel"><option value="0.9">Mais devagar</option><option value="1" selected>Normal</option><option value="1.1">Mais rápida</option></select></label>
  <label>Modo<select id="modo"><option value="continua">Conversa contínua</option><option value="toque">Um toque por vez</option></select></label>
</div>

<div id="conversa">
  <div class="msg aviso">Ao falar, o <b>áudio é enviado a um serviço externo (DeepSeek)</b> para virar texto. Não diga nome, CPF, telefone nem endereço. Se preferir, digite a pergunta.</div>
</div>

<footer>
  <div id="status">Toque em “Começar” para conversar com a Maíra.</div>
  <div id="linha">
    <button class="sec" id="parar" style="display:none">Encerrar</button>
    <button id="mic">Começar</button>
    <button class="sec" id="limpar">Nova conversa</button>
  </div>
  <div id="chips"></div>
  <div id="digitar"><input id="texto" type="text" placeholder="ou digite aqui" maxlength="500" autocomplete="off"><button class="sec" id="enviar">Enviar</button></div>
  <div id="custo"></div>
</footer>
<audio id="player" playsinline></audio>

<script>
const CULTURAS = __CULTURAS__;
const $ = id => document.getElementById(id);
const estado = {pin: sessionStorage.getItem('voz_pin') || '', stream: null, ctx: null, proc: null, chunks: [], gravando: false,
                ocupado: false, falou: false, silencioDesde: 0, inicioGrav: 0, ativo: false, rec: null, tentativas: 0, espera: 0, falando: false};
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
const PT = /\b(que|de|para|o|a|os|as|um|uma|não|nao|com|eu|quero|como|qual|quais|posso|plantar|milho|feijão|feijao|chuva|água|agua|solo|aqui|meu|minha|fazer|tem|vai|é|se|em|no|na|dá|da|do)\b/i;
const LIMIAR = 0.02, SILENCIO_MS = 3500, ESPERA_MS = 9000, MAX_MS = 60000;
function el(tag, cls, txt){const e=document.createElement(tag); if(cls) e.className=cls; if(txt!==undefined) e.textContent=txt; return e;}
function msg(cls, txt, tag){const m=el('div','msg '+cls); if(tag){ const t=el('div','tag',tag); t.style.display='block'; t.style.marginBottom='4px'; m.append(t); } m.append(document.createTextNode(txt)); $('conversa').append(m); m.scrollIntoView({block:'end'}); return m;}
function status(t){$('status').textContent=t;}
function cab(){return {'X-Voz-Pin': estado.pin};}

async function chamar(url, opc){
  const ctl = new AbortController(); const t = setTimeout(()=>ctl.abort(), 100000);
  let r; try{ r = await fetch(url, {...(opc||{}), signal: ctl.signal}); }catch(e){ throw new Error(e.name==='AbortError' ? 'A resposta demorou demais. Tente de novo.' : 'Sem conexão com o servidor.'); } finally { clearTimeout(t); }
  if (r.status === 401){ sessionStorage.removeItem('voz_pin'); estado.pin=''; mostrarPin('PIN incorreto.'); throw new Error('PIN'); }
  if (!r.ok){ let d=''; try{ d=(await r.json()).detail || ''; }catch(e){} throw new Error(d || ('Erro '+r.status)); }
  return r;
}

/* ---------- PIN e listas ---------- */
function mostrarPin(m){ $('pin').style.display='block'; $('conf').style.display='none'; if(m) status(m); }
async function entrar(){
  if(!estado.pin){ mostrarPin(); return; }
  try{ await chamar('/voz/estado', {headers: cab()}); }catch(e){ if(e.message!=='PIN'){ status(e.message); } return; }
  $('pin').style.display='none'; $('conf').style.display='flex'; await listas(); await custo();
}
$('pinok').onclick = () => { estado.pin = $('pinvalor').value.trim(); sessionStorage.setItem('voz_pin', estado.pin); entrar(); };
async function listas(){
  if ($('mun').options.length > 1) return;
  for (const [k,v] of Object.entries(CULTURAS)) { const o=el('option',null,v); o.value=k; $('cult').append(o); }
  try{ const m = await (await fetch('/municipios')).json(); m.sort((a,b)=>(a.nome||a.ponto_id).localeCompare(b.nome||b.ponto_id,'pt-BR'));
       for(const x of m){ const o=el('option',null,x.nome||x.ponto_id); o.value=x.ponto_id; $('mun').append(o);} }catch(e){}
}
async function custo(){
  try{ const d = await (await chamar('/voz/estado',{headers:cab()})).json();
       $('custo').textContent = `Hoje: ${Math.round(d.seg_audio_dia)} s de áudio e ${d.chars_fala_dia} caracteres falados (limites ${d.teto_seg_dia} s e ${d.teto_chars_dia}); custo estimado US$ ${d.custo_estimado_usd_dia}`; }catch(e){}
}

/* ---------- microfone e WAV ---------- */
async function abrirMic(){
  if (estado.stream) return;
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) throw new Error('Este navegador/endereço não libera o microfone (precisa de HTTPS).');
  estado.stream = await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true, noiseSuppression:true, autoGainControl:true}});
  const AC = window.AudioContext || window.webkitAudioContext; estado.ctx = new AC();
  const src = estado.ctx.createMediaStreamSource(estado.stream);
  estado.proc = estado.ctx.createScriptProcessor(4096, 1, 1);
  src.connect(estado.proc); estado.proc.connect(estado.ctx.destination);
  estado.proc.onaudioprocess = ev => {
    if (!estado.gravando) return;
    const d = ev.inputBuffer.getChannelData(0); estado.chunks.push(new Float32Array(d));
    let s=0; for (let i=0;i<d.length;i++) s+=d[i]*d[i]; const rms=Math.sqrt(s/d.length), agora=performance.now();
    if (rms > LIMIAR){ estado.falou=true; estado.silencioDesde=0; } else if (estado.falou && !estado.silencioDesde){ estado.silencioDesde=agora; }
    if (estado.falou && estado.silencioDesde && agora-estado.silencioDesde > SILENCIO_MS) terminarGravacao();
    else if (!estado.falou && agora-estado.inicioGrav > ESPERA_MS) terminarGravacao(true);
    else if (agora-estado.inicioGrav > MAX_MS) terminarGravacao();
  };
}
function fecharMic(){
  if (estado.proc){ estado.proc.disconnect(); estado.proc=null; }
  if (estado.stream){ estado.stream.getTracks().forEach(t=>t.stop()); estado.stream=null; }
  if (estado.ctx){ estado.ctx.close(); estado.ctx=null; }
}
function paraWav(chunks, taxaOrigem){
  let n=0; for(const c of chunks) n+=c.length; const todo=new Float32Array(n); let o=0; for(const c of chunks){ todo.set(c,o); o+=c.length; }
  const alvo=Math.min(48000, Math.round(taxaOrigem)), razao=taxaOrigem/alvo, saida=new Int16Array(Math.floor(n/razao));  // taxa nativa (sem reamostrar) = menos distorção
  for (let i=0;i<saida.length;i++){ const ini=Math.floor(i*razao), fim=Math.min(Math.floor((i+1)*razao), n); let s=0, k=0; for(let j=ini;j<fim;j++){ s+=todo[j]; k++; }
    const v=Math.max(-1,Math.min(1,k?s/k:0)); saida[i]=v<0?v*32768:v*32767; }
  const buf=new ArrayBuffer(44+saida.length*2), dv=new DataView(buf), w=(p,t)=>{for(let i=0;i<t.length;i++) dv.setUint8(p+i,t.charCodeAt(i));};
  w(0,'RIFF'); dv.setUint32(4,36+saida.length*2,true); w(8,'WAVE'); w(12,'fmt '); dv.setUint32(16,16,true); dv.setUint16(20,1,true); dv.setUint16(22,1,true);
  dv.setUint32(24,alvo,true); dv.setUint32(28,alvo*2,true); dv.setUint16(32,2,true); dv.setUint16(34,16,true); w(36,'data'); dv.setUint32(40,saida.length*2,true);
  new Int16Array(buf,44).set(saida); return new Blob([buf], {type:'audio/wav'});
}

/* ---------- fluxo da conversa ---------- */
function juntarTranscritos(lista){
  // o Chrome do Android repete o texto já dito em cada resultado ("fala fala fala"): descarta o que é só o começo de um resultado seguinte
  const t=lista.map(x=>(x||'').replace(/\s+/g,' ').trim()).filter(Boolean), norm=x=>x.toLowerCase();
  const fica=t.filter((x,i)=>!t.slice(i+1).some(y=>norm(y).startsWith(norm(x))));
  let saida=''; for (const x of fica){ if (!norm(saida).includes(norm(x))) saida=(saida+' '+x).trim(); } return saida;
}
function ouvirNavegador(){
  if (!SR){ msg('aviso','Este navegador não tem reconhecimento de voz. Escolha "DeepSeek" em "Ouvir você com" ou digite.'); status('Sem reconhecimento de voz neste navegador.'); return; }
  // Uma "fala" pode ter vários pedaços: se o navegador encerrar sozinho numa pausa, reabrimos e seguimos juntando, até haver silêncio de verdade.
  const t0 = performance.now(); let ultimo = t0, acumulado = '', atual = '', terminou = false, rec = null, vigia = null;
  estado.gravando=true; estado.terminei=false; $('mic').classList.add('rec'); $('mic').textContent='Terminei'; $('parar').style.display='inline-block'; status('Pode falar, sem pressa. Quando terminar, toque em “Terminei”.');
  const textoTotal = () => (acumulado+' '+atual).replace(/\s+/g,' ').trim();
  const espera = setInterval(()=>{ const ag=performance.now(), tem=!!textoTotal();
    if (estado.terminei || (tem && ag-ultimo > SILENCIO_MS) || (!tem && ag-t0 > ESPERA_MS) || ag-t0 > 60000){ terminou=true; try{ rec && rec.stop(); }catch(e){} } }, 300);
  const finalizar = async () => {
    clearInterval(espera); clearTimeout(vigia); estado.gravando=false; $('mic').classList.remove('rec'); $('mic').textContent='Falar'; estado.rec=null;
    const texto = textoTotal();
    if (!texto){ if (estado.ativo && estado.tentativas++ < 1){ return comecarGravacao(); } status('Não ouvi nada. Toque em “Falar” e tente de novo.'); estado.ativo=false; $('parar').style.display='none'; return; }
    estado.tentativas=0; estado.ocupado=true; $('mic').disabled=true;
    try{ await perguntar(texto); }catch(e){ if(e.message!=='PIN'){ msg('aviso', 'Não consegui responder agora. Tente de novo.'); status('Toque em “Falar” e tente de novo.'); estado.ativo=false; } }
    estado.ocupado=false; $('mic').disabled=false; custo();
  };
  const abrir = () => {
    rec = new SR(); estado.rec = rec; rec.lang='pt-BR'; rec.interimResults=true; rec.maxAlternatives=1; rec.continuous=true; atual='';
    rec.onresult = ev => { const t = juntarTranscritos(Array.from(ev.results).map(r => (r[0] ? r[0].transcript : ''))); if (t && t!==atual){ atual=t; ultimo=performance.now(); status('Ouvindo: “'+textoTotal()+'”'); } };
    rec.onerror = ev => { if (ev.error==='not-allowed'||ev.error==='service-not-allowed'){ terminou=true; msg('aviso','O navegador não liberou o microfone (precisa permitir e usar o endereço https).'); } };
    rec.onend = () => {
      acumulado = textoTotal(); atual='';
      const cedo = !terminou && !estado.terminei && estado.gravando && (performance.now()-ultimo) < SILENCIO_MS && (performance.now()-t0) < 60000;
      if (cedo){ try{ abrir(); return; }catch(e){} }          // o navegador cortou numa pausa: continua ouvindo
      finalizar();
    };
    try{ rec.start(); }catch(e){ if (!acumulado){ estado.gravando=false; status('Não consegui iniciar o microfone.'); clearInterval(espera); } else { terminou=true; finalizar(); } }
  };
  vigia = setTimeout(()=>{ terminou=true; try{ rec && rec.abort(); }catch(e){} }, 65000);
  abrir();
}
async function comecarGravacao(){
  if (estado.ocupado || estado.gravando) return;
  if ($('ouvir').value === 'navegador') return ouvirNavegador();
  try{ await abrirMic(); }catch(e){ status(e.message); msg('aviso', e.message); return; }
  estado.chunks=[]; estado.falou=false; estado.silencioDesde=0; estado.inicioGrav=performance.now(); estado.gravando=true;
  $('mic').classList.add('rec'); $('mic').textContent='Terminei'; $('parar').style.display='inline-block'; status('Pode falar, sem pressa. Quando terminar, toque em “Terminei”.');
}
async function terminarGravacao(semFala){
  if (!estado.gravando) return; estado.gravando=false; $('mic').classList.remove('rec'); $('mic').textContent='Falar';
  const chunks=estado.chunks; estado.chunks=[];
  if (semFala || !estado.falou){ status('Não ouvi nada. Toque em “Falar” e tente de novo.'); if(!estado.ativo) $('parar').style.display='none'; estado.ativo=false; fecharMic(); return; }
  estado.ocupado=true; $('mic').disabled=true; status('Entendendo o que você disse...');
  try{
    const wav = paraWav(chunks, estado.ctx.sampleRate);
    const r = await (await chamar('/voz/transcrever',{method:'POST', headers:{...cab(),'Content-Type':'audio/wav'}, body:wav})).json();
    if (!r.texto || (r.texto.length > 8 && !PT.test(r.texto))){ if (r.texto) msg('aviso','Entendi “'+r.texto+'”, que não parece português. Pode repetir, ou escolha “Navegador (português do Brasil)” em “Ouvir você com”.'); status('Não entendi em português. Pode repetir?'); estado.ocupado=false; $('mic').disabled=false; return seguirOuvindo(); }
    await perguntar(r.texto);
  }catch(e){ if(e.message!=='PIN'){ msg('aviso', e.message); status('Algo deu errado. Toque em “Falar” para tentar de novo.'); estado.ativo=false; } }
  estado.ocupado=false; $('mic').disabled=false; custo();
}
async function perguntar(texto, mostrar=true){
  estado.perguntaGrande = texto.trim().split(/\s+/).length >= 12;
  const eSaudacao = !mostrar;
  limparChips(); if (mostrar) msg('eu', texto, 'você');
  status('Pensando...');
  const corpo={mensagem:texto, estado: estado.conversa || null}, mun=$('mun').value, cult=$('cult').value;
  if (mun) corpo.ponto_id=mun; if (mun && cult) corpo.cultura_atual=cult;
  const t0=performance.now(); const temas=[];
  // narra o que realmente está acontecendo (sem prometer nada que não ocorra): a espera deixa de ser silêncio
  temas.push(setTimeout(()=>status('Entendi. Estou olhando os dados do seu local...'), 1200));
  temas.push(setTimeout(()=>status('Conferindo o que isso muda no seu caso...'), 4500));
  temas.push(setTimeout(()=>status('Montando a resposta de um jeito simples...'), 8000));
  if (!eSaudacao && ($('voz').value==='navegador' || $('voz').value==='kokoro')){
    const dizer=async(f)=>{ if (estado.falando) return;
      if ($('voz').value==='kokoro'){ try{ const rr=await chamar('/voz/falar',{method:'POST', headers:{...cab(),'Content-Type':'application/json'}, body:JSON.stringify({texto:f, motor:'kokoro'})});
          if (estado.falando || !estado.esperando) return; const url=URL.createObjectURL(await rr.blob()); const p=$('player'); p.src=url; estado.falando=true;
          await new Promise(res=>{ p.onended=res; p.onerror=res; p.play().catch(res); }); estado.falando=false; URL.revokeObjectURL(url); }catch(e){ estado.falando=false; } return; }
      if (!('speechSynthesis' in window)) return; const u=new SpeechSynthesisUtterance(f); u.lang='pt-BR'; u.rate=parseFloat($('vel').value)||1; const v=vozEscolhida(); if(v) u.voice=v; speechSynthesis.speak(u); };
    estado.esperando=true;
    temas.push(setTimeout(()=>dizer('Só um instante, estou olhando os dados.'), 3000));
    temas.push(setTimeout(()=>dizer('Ainda estou conferindo, já te respondo.'), 8500));
  }
  let r;
  try{ r = await (await chamar('/conversa',{method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(corpo)})).json(); }
  finally{ temas.forEach(clearTimeout); estado.esperando=false; }
  estado.conversa = r.estado;
  const rotulo = 'Maíra · assistente automática' + ' · ' + ((performance.now()-t0)/1000).toFixed(1) + ' s' + (r.origem==='llm' ? ' · IA' : '');
  msg('sist', r.resposta, rotulo);
  mostrarChips(r.chips || []);
  await falar(r.resposta);
  await seguirOuvindo();
}
function limparChips(){ $('chips').textContent=''; }
function mostrarChips(chips){
  limparChips();
  for (const c of chips){ const b=el('button',null,c.rotulo); b.onclick=async()=>{
      if (estado.ocupado) return; liberarAudio(); estado.ocupado=true; estado.ativo=$('modo').value==='continua';
      if (estado.gravando){ if(estado.rec){ try{estado.rec.abort();}catch(e){} estado.rec=null; } estado.gravando=false; estado.chunks=[]; $('mic').classList.remove('rec'); }
      try{ await perguntar(c.texto); }catch(e){ if(e.message!=='PIN') msg('aviso', e.message); }
      estado.ocupado=false; custo(); };
    $('chips').append(b); }
}
async function iniciarConversa(){
  // não fala sozinha: só abre o microfone. Quem cumprimenta primeiro é você ("bom dia"), e ela responde e se apresenta.
  estado.conversa=null; estado.iniciada=true; estado.parou=false; estado.ativo=$('modo').value==='continua';
  status('Pode falar. Comece dizendo, por exemplo, “bom dia”.'); $('mic').disabled=false;
  await comecarGravacao();
}
async function falar(texto){
  const modo=$('voz').value; if (modo==='nenhuma') return;
  estado.falando=true; try{ await falarDe(texto, modo); } finally { estado.falando=false; }
}
async function falarDe(texto, modo){
  status('Respondendo em voz...');
  if (modo==='navegador'){
    const frases=(texto.replace(/\s+/g,' ').match(/[^.!?;:]+[.!?;:]?/g)||[texto]).map(x=>x.trim()).filter(Boolean);
    const juntas=[]; let atual=''; for(const f of frases){ if((atual+' '+f).length>170 && atual){ juntas.push(atual); atual=f; } else atual=(atual+' '+f).trim(); } if(atual) juntas.push(atual);
    for (let i=0;i<40 && speechSynthesis.speaking;i++) await new Promise(r=>setTimeout(r,100));   // deixa terminar a frase de espera
    speechSynthesis.cancel();
    for (const parte of juntas){ if (!estado.ativo && $('modo').value==='continua' && estado.parou) break;
      await new Promise(res => { let feito=false; const fim=()=>{ if(!feito){ feito=true; clearInterval(sond); clearTimeout(lim); res(); } };
        const u=new SpeechSynthesisUtterance(parte); u.lang='pt-BR'; u.rate=parseFloat($('vel').value)||1; const v=vozEscolhida(); if(v) u.voice=v;
        u.onend=fim; u.onerror=fim; const lim=setTimeout(fim, 4000+parte.length*110);
        let parados=0; const sond=setInterval(()=>{ if(!speechSynthesis.speaking && !speechSynthesis.pending){ if(++parados>=3) fim(); } else parados=0; }, 300);
        speechSynthesis.speak(u); }); }
    return;
  }
  try{
    // lê a resposta INTEIRA, como está escrita na tela, em pedaços curtos. Todos os pedaços começam a ser gerados já (em fila),
    // sem esperar o anterior tocar: assim não há silêncio a cada ponto final.
    const frases=(texto.replace(/\s+/g,' ').match(/[^.!?;:]+[.!?;:]?/g)||[texto]).map(x=>x.trim()).filter(Boolean);
    let ini0=frases[0]; const vi=ini0.search(/[,:]\s/); if (ini0.length>70 && vi>20 && vi<ini0.length-25){ frases.splice(0,1,ini0.slice(0,vi+1), ini0.slice(vi+1).trim()); }   // 1º pedaço curto: começa a falar mais cedo
    const partes=[frases[0]]; let atual=''; for (const f of frases.slice(1)){ if (atual && (atual+' '+f).length>170){ partes.push(atual); atual=f; } else atual=(atual+' '+f).trim(); } if (atual) partes.push(atual);
    const pedir=(t)=>chamar('/voz/falar',{method:'POST', headers:{...cab(),'Content-Type':'application/json'}, body:JSON.stringify({texto:t, motor: modo==='kokoro' ? 'kokoro' : 'deepseek'})}).then(r=>r.blob());
    const fila=[]; let cadeia=Promise.resolve();
    for (const t of partes){ const pr=cadeia.then(()=>estado.parou?null:pedir(t)); fila.push(pr); cadeia=pr.catch(()=>null); }
    for (let i=0;i<fila.length;i++){
      const blob=await fila[i]; if (!blob || estado.parou) break;
      const url=URL.createObjectURL(blob); const p=$('player'); p.src=url;
      await new Promise(res => { p.onended=res; p.onerror=res; p.play().catch(res); });
      URL.revokeObjectURL(url);
    }
  }catch(e){ if(e.message==='PIN') return;
    if (modo==='kokoro' && 'speechSynthesis' in window){ msg('aviso','A voz da Dora não respondeu; usando a voz do celular desta vez.'); return falarDe(texto,'navegador'); }
    msg('aviso','Não consegui falar em voz ('+e.message+'). A resposta está escrita acima.'); }
}
async function seguirOuvindo(){
  estado.ocupado=false; $('mic').disabled=false;     // libera ANTES de ouvir de novo (senão comecarGravacao() sai sem fazer nada)
  if ($('modo').value==='continua' && estado.ativo){ await new Promise(r=>setTimeout(r,500)); if (!estado.ativo) return; return comecarGravacao(); }
  status('Toque em “Falar” para continuar.'); $('parar').style.display='none'; estado.ativo=false; fecharMic();
}
function vozesPt(){ return speechSynthesis.getVoices().filter(x=>/^pt[-_]BR$/i.test(x.lang) || /portugu[eê]s.*brasil|brazil/i.test(x.name)); }
function vozEscolhida(){ const l=vozesPt(), nome=$('vozbr').value; if(!l.length) return null; if(nome){ const v=l.find(x=>x.name===nome); if(v) return v; }
  const boas=/(natural|neural|online|google|francisca|antonio|thalita|luciana|felipe|raquel|joana)/i; return l.find(x=>boas.test(x.name)) || l[0]; }
function preencherVozes(){ const s=$('vozbr'); if(!s) return; const atual=s.value; s.textContent=''; const a=el('option',null,'(automática)'); a.value=''; s.append(a);
  for(const v of vozesPt()){ const o=el('option',null,v.name); o.value=v.name; s.append(o); } s.value=atual; }
if ('speechSynthesis' in window){ speechSynthesis.onvoiceschanged=preencherVozes; preencherVozes(); }
function liberarAudio(){ const p=$('player'); p.src='data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA='; p.play().catch(()=>{}); }

$('mic').onclick = async () => { if (estado.gravando && estado.rec && $('ouvir').value==='navegador'){ estado.terminei=true; return; } if (estado.falando){ speechSynthesis.cancel(); $('player').pause(); return; } liberarAudio(); estado.parou=false; if (!estado.iniciada){ await iniciarConversa(); return; } if (estado.gravando && estado.rec){ estado.rec.stop(); } else if (estado.gravando){ terminarGravacao(); } else { estado.ativo = true; comecarGravacao(); } };
$('parar').onclick = () => { estado.ativo=false; estado.parou=true; speechSynthesis.cancel(); if (estado.rec){ try{ estado.rec.abort(); }catch(e){} estado.rec=null; } if (estado.gravando) { estado.falou=false; estado.gravando=false; estado.chunks=[]; $('mic').classList.remove('rec'); $('mic').textContent='Falar'; } fecharMic(); speechSynthesis.cancel(); $('player').pause(); $('parar').style.display='none'; status('Conversa encerrada.'); };
$('limpar').onclick = async () => { estado.ativo=false; if (estado.rec){ try{estado.rec.abort();}catch(e){} estado.rec=null; } estado.gravando=false; fecharMic(); speechSynthesis.cancel(); $('player').pause(); limparChips(); $('conversa').querySelectorAll('.msg:not(.aviso)').forEach(m=>m.remove()); estado.iniciada=false; estado.conversa=null; $('mic').classList.remove('rec'); $('mic').textContent='Começar'; status('Toque em “Começar” para uma nova conversa.'); };
$('enviar').onclick = async () => { const t=$('texto').value.trim(); if(!t||estado.ocupado) return; $('texto').value=''; estado.ocupado=true; liberarAudio(); estado.iniciada=true;
  try{ await perguntar(t); }catch(e){ if(e.message!=='PIN') msg('aviso', e.message); } estado.ocupado=false; custo(); };
$('texto').addEventListener('keydown', e=>{ if(e.key==='Enter'){ e.preventDefault(); $('enviar').click(); } });
if (!SR) { $('ouvir').value = 'deepseek'; }
entrar();
</script>
</body>
</html>
"""


def renderizar(culturas: dict[str, str]) -> str:
    """Insere as culturas (id -> rótulo) como JSON seguro dentro de <script> (escapa `<`, `>` e `&`)."""
    seguro = json.dumps(culturas, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return PAGINA.replace("__CULTURAS__", seguro)
