"""A single self-contained HTML viewer for a GLB (WO-100 deliverable 4;
charter 38 sec. 1 decision 6 -- the graphite/AD-31 posture: inline
everything, zero external requests, no CDN, no build step).

The GLB is embedded as base64 (so the page makes NO network request, not
even a relative fetch that a ``file://`` origin might block), decoded in
the browser, and drawn with a small dependency-free WebGL2 renderer:
orbit/pan/zoom, flat shading computed in-shader from screen-space
derivatives (so the GLB needs no normals), a per-part colour, and
part-name hover via an id-colour picking pass over the GLB node names.

The generated source is ASCII-only and contains no ``http``/``//`` host
reference of any kind; `tests/backends/test_wo100_viewer.py` asserts both.
"""

from __future__ import annotations

import base64

from regolith.logging_setup import get_logger

_log = get_logger(__name__)

# The renderer JS. Kept as ONE ASCII template; the GLB bytes and the
# document title are the only injected values. No external reference.
_VIEWER_JS = r"""
'use strict';
function b64ToBuf(b64){
  var bin = atob(b64);
  var len = bin.length;
  var bytes = new Uint8Array(len);
  for (var i=0;i<len;i++){ bytes[i]=bin.charCodeAt(i); }
  return bytes.buffer;
}
function parseGlb(buf){
  var dv = new DataView(buf);
  var magic = dv.getUint32(0, true);
  if (magic !== 0x46546c67){ throw new Error('not a GLB'); }
  var length = dv.getUint32(8, true);
  var off = 12, json=null, bin=null;
  while (off < length){
    var clen = dv.getUint32(off, true);
    var ctype = dv.getUint32(off+4, true);
    var cdata = buf.slice(off+8, off+8+clen);
    if (ctype === 0x4e4f534a){ json = JSON.parse(new TextDecoder('utf-8').decode(cdata)); }
    else if (ctype === 0x004e4942){ bin = cdata; }
    off += 8 + clen;
  }
  return {json: json, bin: bin};
}
function accessorArray(gltf, bin, index, ArrayType){
  var acc = gltf.accessors[index];
  var view = gltf.bufferViews[acc.bufferView];
  var off = (view.byteOffset||0) + (acc.byteOffset||0);
  var comps = ({SCALAR:1, VEC2:2, VEC3:3}[acc.type]) || 1;
  return new ArrayType(bin, off, acc.count*comps);
}
function mat4mul(a,b){
  var o=new Float32Array(16);
  for(var r=0;r<4;r++){for(var c=0;c<4;c++){
    var s=0; for(var k=0;k<4;k++){ s+=a[k*4+r]*b[c*4+k]; } o[c*4+r]=s;
  }}
  return o;
}
function perspective(fovy, aspect, near, far){
  var f=1.0/Math.tan(fovy/2), nf=1.0/(near-far);
  return new Float32Array([f/aspect,0,0,0, 0,f,0,0, 0,0,(far+near)*nf,-1, 0,0,2*far*near*nf,0]);
}
function lookAt(eye,center,up){
  var zx=eye[0]-center[0], zy=eye[1]-center[1], zz=eye[2]-center[2];
  var zl=Math.hypot(zx,zy,zz)||1; zx/=zl; zy/=zl; zz/=zl;
  var xx=up[1]*zz-up[2]*zy, xy=up[2]*zx-up[0]*zz, xz=up[0]*zy-up[1]*zx;
  var xl=Math.hypot(xx,xy,xz)||1; xx/=xl; xy/=xl; xz/=xl;
  var yx=zy*xz-zz*xy, yy=zz*xx-zx*xz, yz=zx*xy-zy*xx;
  return new Float32Array([xx,yx,zx,0, xy,yy,zy,0, xz,yz,zz,0,
    -(xx*eye[0]+xy*eye[1]+xz*eye[2]),
    -(yx*eye[0]+yy*eye[1]+yz*eye[2]),
    -(zx*eye[0]+zy*eye[1]+zz*eye[2]), 1]);
}
function main(glbB64){
  var glb = parseGlb(b64ToBuf(glbB64));
  var gltf = glb.json, bin = glb.bin;
  var canvas = document.getElementById('c');
  var gl = canvas.getContext('webgl2', {antialias:true, preserveDrawingBuffer:true});
  if(!gl){ document.getElementById('msg').textContent='WebGL2 unavailable'; return; }

  var vsrc = '#version 300 es\n'+
    'in vec3 p; uniform mat4 mvp; uniform mat4 model; out vec3 wp;'+
    'void main(){ wp=(model*vec4(p,1.0)).xyz; gl_Position=mvp*vec4(p,1.0); }';
  var fsrc = '#version 300 es\nprecision highp float;'+
    'in vec3 wp; uniform vec3 col; uniform int pick; out vec4 o;'+
    'void main(){'+
    ' vec3 n=normalize(cross(dFdx(wp),dFdy(wp)));'+
    ' if(pick==1){ o=vec4(col,1.0); return; }'+
    ' float d=clamp(abs(n.z)*0.6+0.4,0.0,1.0);'+
    ' o=vec4(col*d,1.0); }';
  function sh(type,src){ var s=gl.createShader(type); gl.shaderSource(s,src); gl.compileShader(s); return s; }
  var prog=gl.createProgram();
  gl.attachShader(prog, sh(gl.VERTEX_SHADER, vsrc));
  gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, fsrc));
  gl.bindAttribLocation(prog,0,'p'); gl.linkProgram(prog); gl.useProgram(prog);
  var uMvp=gl.getUniformLocation(prog,'mvp');
  var uModel=gl.getUniformLocation(prog,'model');
  var uCol=gl.getUniformLocation(prog,'col');
  var uPick=gl.getUniformLocation(prog,'pick');

  // Build one draw record per scene node.
  var scene = gltf.scenes[gltf.scene||0];
  var draws=[]; var names=[];
  var lo=[1e30,1e30,1e30], hi=[-1e30,-1e30,-1e30];
  for(var ni=0; ni<scene.nodes.length; ni++){
    var node=gltf.nodes[scene.nodes[ni]];
    var mesh=gltf.meshes[node.mesh];
    var prim=mesh.primitives[0];
    var pos=accessorArray(gltf,bin,prim.attributes.POSITION,Float32Array);
    var idx=accessorArray(gltf,bin,prim.indices,Uint32Array);
    var m = node.matrix ? new Float32Array(node.matrix) :
      new Float32Array([1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]);
    var vao=gl.createVertexArray(); gl.bindVertexArray(vao);
    var vb=gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER,vb);
    gl.bufferData(gl.ARRAY_BUFFER,pos,gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0,3,gl.FLOAT,false,0,0);
    var ib=gl.createBuffer(); gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,ib);
    gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,idx,gl.STATIC_DRAW);
    var name = node.name || ('part '+ni);
    names.push(name);
    var acc=gltf.accessors[prim.attributes.POSITION];
    var mn=acc.min, mx=acc.max;
    for(var a=0;a<3;a++){ if(mn){lo[a]=Math.min(lo[a],mn[a]); hi[a]=Math.max(hi[a],mx[a]);} }
    // Deterministic per-node hue.
    var h=(ni*0.61803398875)%1.0;
    var col=hsv(h,0.55,0.9);
    draws.push({vao:vao, count:idx.length, model:m, col:col,
      id:[((ni+1)&255)/255,(((ni+1)>>8)&255)/255,(((ni+1)>>16)&255)/255]});
  }
  function hsv(h,s,v){
    var i=Math.floor(h*6), f=h*6-i, p=v*(1-s), q=v*(1-f*s), t=v*(1-(1-f)*s);
    var r,g,b; switch(i%6){case 0:r=v;g=t;b=p;break;case 1:r=q;g=v;b=p;break;
      case 2:r=p;g=v;b=t;break;case 3:r=p;g=q;b=v;break;case 4:r=t;g=p;b=v;break;
      default:r=v;g=p;b=q;} return [r,g,b];
  }
  var center=[(lo[0]+hi[0])/2,(lo[1]+hi[1])/2,(lo[2]+hi[2])/2];
  var radius=Math.max(1.0,Math.hypot(hi[0]-lo[0],hi[1]-lo[1],hi[2]-lo[2])/2);

  var cam={yaw:0.7, pitch:0.5, dist:radius*3, panx:0, pany:0};
  function eye(){
    var cp=Math.cos(cam.pitch), sp=Math.sin(cam.pitch);
    var cy=Math.cos(cam.yaw), sy=Math.sin(cam.yaw);
    return [center[0]+cam.dist*cp*sy, center[1]+cam.dist*sp, center[2]+cam.dist*cp*cy];
  }
  gl.enable(gl.DEPTH_TEST);
  function resize(){
    var dpr=window.devicePixelRatio||1;
    canvas.width=canvas.clientWidth*dpr; canvas.height=canvas.clientHeight*dpr;
  }
  function draw(pickMode){
    resize();
    gl.viewport(0,0,canvas.width,canvas.height);
    gl.clearColor(pickMode?0:0.09, pickMode?0:0.09, pickMode?0:0.11, 1);
    gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
    var ctr=[center[0]+cam.panx, center[1]+cam.pany, center[2]];
    var e=eye(); e[0]+=cam.panx; e[1]+=cam.pany;
    var proj=perspective(0.9, canvas.width/canvas.height, radius*0.05, radius*50);
    var view=lookAt(e, ctr, [0,1,0]);
    var vp=mat4mul(proj,view);
    gl.uniform1i(uPick, pickMode?1:0);
    for(var i=0;i<draws.length;i++){
      var d=draws[i];
      gl.uniformMatrix4fv(uMvp,false, mat4mul(vp,d.model));
      gl.uniformMatrix4fv(uModel,false, d.model);
      gl.uniform3fv(uCol, pickMode?d.id:d.col);
      gl.bindVertexArray(d.vao);
      gl.drawElements(gl.TRIANGLES, d.count, gl.UNSIGNED_INT, 0);
    }
  }
  var dragging=false, panning=false, lastx=0, lasty=0;
  canvas.addEventListener('mousedown',function(ev){
    dragging=true; panning=(ev.button===2||ev.shiftKey); lastx=ev.clientX; lasty=ev.clientY;});
  window.addEventListener('mouseup',function(){dragging=false;});
  canvas.addEventListener('contextmenu',function(ev){ev.preventDefault();});
  canvas.addEventListener('mousemove',function(ev){
    if(dragging){
      var dx=ev.clientX-lastx, dy=ev.clientY-lasty; lastx=ev.clientX; lasty=ev.clientY;
      if(panning){ cam.panx-=dx*radius*0.003; cam.pany+=dy*radius*0.003; }
      else { cam.yaw-=dx*0.01; cam.pitch=Math.max(-1.5,Math.min(1.5,cam.pitch+dy*0.01)); }
      draw(false);
    } else { hover(ev); }
  });
  canvas.addEventListener('wheel',function(ev){
    ev.preventDefault(); cam.dist*=(ev.deltaY>0?1.1:0.9);
    cam.dist=Math.max(radius*0.2,Math.min(radius*30,cam.dist)); draw(false);},{passive:false});
  var tip=document.getElementById('tip');
  function hover(ev){
    draw(true);
    var dpr=window.devicePixelRatio||1;
    var px=Math.floor(ev.offsetX*dpr), py=Math.floor(canvas.height-ev.offsetY*dpr);
    var pix=new Uint8Array(4); gl.readPixels(px,py,1,1,gl.RGBA,gl.UNSIGNED_BYTE,pix);
    var id=pix[0]+(pix[1]<<8)+(pix[2]<<16);
    draw(false);
    if(id>0 && id<=names.length){
      tip.textContent=names[id-1]; tip.style.left=(ev.offsetX+12)+'px';
      tip.style.top=(ev.offsetY+12)+'px'; tip.style.display='block';
    } else { tip.style.display='none'; }
  }
  window.addEventListener('resize',function(){draw(false);});
  // Legend.
  var leg=document.getElementById('legend');
  for(var i=0;i<names.length;i++){
    var c=draws[i].col; var row=document.createElement('div');
    row.innerHTML='<span class="sw" style="background:rgb('+
      Math.round(c[0]*255)+','+Math.round(c[1]*255)+','+Math.round(c[2]*255)+')"></span>'+names[i];
    leg.appendChild(row);
  }
  draw(false);
}
"""

_VIEWER_CSS = r"""
html,body{margin:0;height:100%;background:#16181d;color:#dfe3ea;font:13px sans-serif;}
#c{width:100vw;height:100vh;display:block;cursor:grab;}
#legend{position:fixed;top:10px;left:10px;background:rgba(0,0,0,.45);
  padding:8px 10px;border-radius:6px;max-height:60vh;overflow:auto;}
#legend .sw{display:inline-block;width:11px;height:11px;margin-right:6px;
  border-radius:2px;vertical-align:middle;}
#legend div{margin:2px 0;}
#tip{position:fixed;display:none;background:#000;color:#fff;padding:2px 6px;
  border-radius:3px;pointer-events:none;font-size:12px;}
#msg{position:fixed;bottom:10px;left:10px;color:#f88;}
h1{position:fixed;bottom:8px;right:12px;margin:0;font-size:12px;
  font-weight:normal;color:#8b93a3;}
"""


def viewer_html(glb_bytes: bytes, title: str) -> bytes:
    """One self-contained ``viewer.html`` for ``glb_bytes`` (ASCII, zero
    external requests). ``title`` names the subject in the tab and corner.
    """
    b64 = base64.b64encode(glb_bytes).decode("ascii")
    safe_title = (
        "".join(c for c in title if 32 <= ord(c) < 127)
        .replace("<", "")
        .replace(">", "")
    )
    html = (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">\n'
        f"<title>{safe_title} -- 3D</title>\n"
        f"<style>{_VIEWER_CSS}</style>\n</head>\n<body>\n"
        '<canvas id="c"></canvas>\n<div id="legend"></div>\n'
        '<div id="tip"></div>\n<div id="msg"></div>\n'
        f"<h1>{safe_title}</h1>\n"
        f"<script>{_VIEWER_JS}\n"
        f'main("{b64}");</script>\n</body></html>\n'
    )
    data = html.encode("ascii")
    _log.info("viewer: %s -> %d bytes (GLB %d b64)", title, len(data), len(b64))
    return data
