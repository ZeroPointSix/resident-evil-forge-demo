/* Real Blockbench load/save/export/reload and geometry checks in Chromium. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const crypto = require('node:crypto');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || '/home/daytona/blockbench-tools/node_modules/playwright');
const appRoot = process.env.BLOCKBENCH_ROOT || '/home/daytona/blockbench-tools/blockbench';
const out = process.argv[2] || '/home/daytona/re-forge-blockbench';
const intermediate = JSON.parse(fs.readFileSync(path.join(out,'intermediate.json')));
const mime = {'.html':'text/html','.js':'text/javascript','.json':'application/json','.css':'text/css','.png':'image/png','.svg':'image/svg+xml'};
const server = http.createServer((req,res)=>{
  const relative = decodeURIComponent(req.url.split('?')[0]);
  const file = path.resolve(appRoot, '.'+(relative === '/' ? '/index.html' : relative));
  if (!file.startsWith(appRoot+path.sep)) {res.writeHead(403);res.end();return;}
  fs.readFile(file,(err,data)=>{res.writeHead(err?404:200,{'Content-Type':mime[path.extname(file)]||'application/octet-stream'});res.end(err?'':data);});
});

async function run() {
  await new Promise(resolve=>server.listen(8124,'127.0.0.1',resolve));
  const browser = await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,
    args:['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-dev-shm-usage']});
  try {
    const page = await browser.newPage({viewport:{width:1600,height:1000}});
    const errors=[];
    page.on('pageerror',e=>errors.push({message:e.message,stack:e.stack}));
    await page.goto('http://127.0.0.1:8124/',{waitUntil:'load',timeout:60000});
    await page.waitForFunction(()=>typeof Blockbench !== 'undefined' && Blockbench.version && typeof Codecs !== 'undefined' && Codecs.project && Formats.bedrock);
    const report = {blockbench_version:await page.evaluate(()=>Blockbench.version),
      browser_version:browser.version(),source_commit:intermediate.source_commit,
      source_blend_sha256:intermediate.source_blend_sha256,
      format:'Bedrock 1.12.0 cube geometry, supported by GeckoLib 4',
      bbmodel_editor_format:'bedrock (opens in stock Blockbench, plugin optional)',
      game_runtime_tested:false,models:{}};
    for (const [name, model] of Object.entries(intermediate.models)) {
      const result = await page.evaluate(async ({name,model,materials})=>{
        if (Dialog.open) Dialog.open.hide();
        if (Project) {Project.saved=true;await Project.close();}
        newProject(Formats.bedrock);
        Project.name=name;
        Project.geometry_name='re_demo.'+name+'_blockout';
        Project.texture_width=64;Project.texture_height=64;Project.box_uv=false;
        Project.credit='Original approved blockout / RE Forge art review only';
        const materialNames=Object.keys(materials);
        const canvas=document.createElement('canvas');canvas.width=canvas.height=64;
        const ctx=canvas.getContext('2d');
        ctx.fillStyle='#000000';ctx.fillRect(0,0,64,64);
        const srgb=x=>Math.round(255*(x<=.0031308?12.92*x:1.055*x**(1/2.4)-.055));
        for(const [i,key] of materialNames.entries()){
          ctx.fillStyle='rgb('+materials[key].map(srgb).join(',')+')';
          ctx.fillRect((i%8)*8,Math.floor(i/8)*8,8,8);
        }
        const palette=canvas.toDataURL('image/png');
        const texture=new Texture({name:name+'_palette.png',keep_size:true}).fromDataURL(palette).add(false);
        await new Promise(resolve=>setTimeout(resolve,300));
        const root=new Group({name:'root',origin:[0,0,0]}).init();
        const groups={};
        for(const part of model.parts){
          groups[part.name]=new Group({name:part.name,origin:part.pivot}).addTo(root).init();
        }
        for(const data of model.cubes){
          const cube=new Cube({name:data.name,from:data.from,to:data.to,origin:data.origin,
            rotation:data.rotation,autouv:0,box_uv:false}).addTo(groups[data.part]).init();
          const i=materialNames.indexOf(data.material),u=(i%8)*8+2,v=Math.floor(i/8)*8+2;
          for(const face of Object.values(cube.faces)){face.texture=texture.uuid;face.uv=[u,v,u+4,v+4];}
        }
        Canvas.updateAll();
        scene.updateMatrixWorld(true);
        function worldVertices(){
          return Cube.all.map(cube=>{
            const attr=cube.mesh.geometry.attributes.position;
            return Array.from({length:attr.count},(_,i)=>new THREE.Vector3().fromBufferAttribute(attr,i).applyMatrix4(cube.mesh.matrixWorld).toArray());
          });
        }
        const before=worldVertices();
        let maxCornerError=0;
        for(let i=0;i<model.cubes.length;i++){
          for(const expected of model.cubes[i].expected_corners){
            const distance=Math.min(...before[i].map(p=>Math.hypot(...p.map((v,a)=>v-expected[a]))));
            maxCornerError=Math.max(maxCornerError,distance);
          }
        }
        if(maxCornerError>.002)throw Error(name+' coordinate mapping error '+maxCornerError);
        const geo=Codecs.bedrock.compile({raw:true});
        const bbmodel=Codecs.project.compile({raw:true});
        Project.saved=true;await Project.close();
        Codecs.project.load(JSON.parse(JSON.stringify(bbmodel)),{path:name+'.bbmodel',name:name+'.bbmodel',no_file:true});
        await new Promise(resolve=>setTimeout(resolve,250));
        Canvas.updateAll();scene.updateMatrixWorld(true);
        const bbCount=Cube.all.length;
        const bbTextureCount=Texture.all.length;
        const bbGeo=Codecs.bedrock.compile({raw:true});
        if(JSON.stringify(geo)!==JSON.stringify(bbGeo))throw Error(name+' BBModel round trip changed geometry');
        Project.saved=true;await Project.close();
        Codecs.bedrock.load(JSON.parse(JSON.stringify(geo)),{path:name+'.geo.json',name:name+'.geo.json',no_file:true},false);
        new Texture({name:name+'_palette.png',keep_size:true}).fromDataURL(palette).add(false);
        await new Promise(resolve=>setTimeout(resolve,250));
        Canvas.updateAll();scene.updateMatrixWorld(true);
        const after=worldVertices();
        let reloadError=0;
        for(let i=0;i<before.length;i++)for(let j=0;j<before[i].length;j++){
          reloadError=Math.max(reloadError,Math.hypot(...before[i][j].map((v,a)=>v-after[i][j][a])));
        }
        if(reloadError>.002)throw Error(name+' GEO round trip changed vertices '+reloadError);
        if(geo.format_version!=='1.12.0')throw Error('Unexpected target version');
        const bounds=new THREE.Box3();
        for(const points of after)for(const p of points)bounds.expandByPoint(new THREE.Vector3(...p));
        const allCorners=after.flat();
        const roundtripGeo=Codecs.bedrock.compile({raw:true});
        const corners=Object.fromEntries(Cube.all.map((cube,i)=>[model.cubes[i].name,after[i]]));
        return {geo,bbmodel,palette,corners,
          stats:{source_vertices:model.source_vertices,source_parts:model.parts.length,
            cubes:Cube.all.length,bones:Group.all.length,logical_vertices:Cube.all.length*8,
            render_vertices:Cube.all.length*24,quad_faces:Cube.all.length*6,triangles:Cube.all.length*12,
            bbmodel_reload_cubes:bbCount,bbmodel_embedded_textures:bbTextureCount,
            geo_reload_cubes:Cube.all.length,max_source_mapping_error_units:maxCornerError,
            max_geo_reload_vertex_error_units:reloadError,
            bounds_bb:[bounds.min.toArray(),bounds.max.toArray()],
            dimensions_m:bounds.getSize(new THREE.Vector3()).toArray().map(x=>x/16),
            bbmodel_roundtrip_identical:true,geo_reimport_passed:true,
            all_cubes_solid:Cube.all.every(c=>c.size().every(v=>v>0)),
            all_faces_textured:Cube.all.every(c=>Object.values(c.faces).every(f=>f.texture!==null)),
            no_poly_mesh:!geo['minecraft:geometry'][0].bones.some(b=>b.poly_mesh),
            rest_pose_only:true}};
      },{name,model,materials:intermediate.materials_linear_rgb});
      assert.equal(result.stats.cubes,model.cubes.length);
      assert.equal(result.stats.bbmodel_embedded_textures,1);
      assert(result.stats.all_cubes_solid && result.stats.all_faces_textured && result.stats.no_poly_mesh);
      fs.writeFileSync(path.join(out,name+'.geo.json'),JSON.stringify(result.geo,null,2)+'\n');
      fs.writeFileSync(path.join(out,name+'.bbmodel'),JSON.stringify(result.bbmodel,null,2)+'\n');
      fs.writeFileSync(path.join(out,name+'_palette.png'),Buffer.from(result.palette.split(',')[1],'base64'));
      fs.writeFileSync(path.join(out,name+'_bb_vertices.json'),JSON.stringify(result.corners));
      report.models[name]=result.stats;
      console.log('BLOCKBENCH_ROUNDTRIP_OK',name,JSON.stringify(result.stats));
    }
    report.app_errors=errors;
    report.file_sha256={};
    for(const name of Object.keys(intermediate.models))for(const suffix of ['.geo.json','.bbmodel','_palette.png']){
      const file=name+suffix;report.file_sha256[file]=crypto.createHash('sha256').update(fs.readFileSync(path.join(out,file))).digest('hex');
    }
    fs.writeFileSync(path.join(out,'blockbench_validation.json'),JSON.stringify(report,null,2)+'\n');
    console.log('ALL_BLOCKBENCH_CHECKS_PASSED');
  } finally {await browser.close();}
}
run().then(()=>server.close()).catch(error=>{console.error(error);server.close();process.exit(1);});
