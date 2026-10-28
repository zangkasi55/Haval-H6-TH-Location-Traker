import assert from "node:assert/strict";
import {createServer} from "node:http";
import {readFile,mkdir} from "node:fs/promises";
import {resolve,dirname,extname,sep} from "node:path";
import {fileURLToPath} from "node:url";
import {chromium} from "playwright";
import {syntheticMapArchive} from "./synthetic_map_fixture.mjs";

const root=resolve(dirname(fileURLToPath(import.meta.url)),".."),archive=syntheticMapArchive();
const server=createServer(async(request,response)=>{
  const path=new URL(request.url,"http://127.0.0.1").pathname;
  if(path==="/local/gwm-maps/test.pmtiles"){
    const range=/^bytes=(\d+)-(\d*)$/.exec(request.headers.range || "");
    if(!range){response.writeHead(200,{"content-type":"application/octet-stream","content-length":archive.length}).end(archive);return;}
    const start=Number(range[1]),end=Math.min(archive.length-1,range[2]?Number(range[2]):archive.length-1);
    if(start>end || start>=archive.length){response.writeHead(416,{"content-range":`bytes */${archive.length}`}).end();return;}
    response.writeHead(206,{"content-type":"application/octet-stream","content-range":`bytes ${start}-${end}/${archive.length}`,"content-length":end-start+1,"accept-ranges":"bytes"}).end(archive.subarray(start,end+1));return;
  }
  const file=resolve(root,"."+decodeURIComponent(path));
  if(!file.startsWith(root+sep)){response.writeHead(403).end();return;}
  try{
    const data=await readFile(file);
    const types={".html":"text/html; charset=utf-8",".json":"application/json",".js":"text/javascript",".css":"text/css"};
    response.writeHead(200,{"content-type":types[extname(file)] || "application/octet-stream"}).end(data);
  }catch(error){if(error.code!=="ENOENT")console.error(error);response.writeHead(404).end();}
});
await new Promise(done=>server.listen(0,"127.0.0.1",done));
const origin="http://127.0.0.1:"+server.address().port;
let browser;
try{
  browser=await chromium.launch({headless:true,channel:process.platform==="win32"?"msedge":undefined});
  const context=await browser.newContext({viewport:{width:1280,height:1040},locale:"en-US",timezoneId:"Asia/Bangkok"});
  const blocked=[],errors=[];
  await context.route("**/*",route=>{
    if(new URL(route.request().url()).origin===origin)return route.continue();
    blocked.push(route.request().url());return route.abort();
  });
  const page=await context.newPage();page.on("pageerror",error=>errors.push(error.message));
  const output=resolve(root,"docs","images");await mkdir(output,{recursive:true});
  for(const mode of ["setup","journeys","stops","no-gps","icon"]){
    await page.goto(origin+"/docs/demo/index.html?mode="+mode);
    await page.waitForSelector('body[data-ready="true"]');
    if(["journeys","stops"].includes(mode)){
      await page.locator("haval-journey-card .car-marker").waitFor();
      await page.waitForFunction(()=>Object.values(document.querySelector("haval-journey-card")._baseLayer?._tiles || {}).some(tile=>tile.loaded));
      if(mode==="journeys"){
        await page.getByRole("button",{name:"Car",exact:true}).click();
        await page.getByRole("button",{name:"Journey",exact:true}).click();
        await page.evaluate(()=>document.querySelector("haval-journey-card")._car.openPopup());
        assert.equal(await page.locator("haval-journey-card .stop-marker").count(),3);
      }
      else{
        await page.locator("haval-journey-card .history summary").click();
        await page.locator("haval-journey-card [data-stop]").last().click();
      }
    }
    if(mode==="no-gps"){
      assert.equal(await page.locator("haval-journey-card .car-marker").count(),0);
      assert.equal(await page.locator("haval-journey-card .leaflet-tile").count(),0);
    }
    if(mode==="icon"){
      const brand=resolve(root,"custom_components","haval_h6_th_location_tracker","brand");await mkdir(brand,{recursive:true});
      await page.locator("#icon").screenshot({path:resolve(brand,"icon.png")});
    }else await page.screenshot({path:resolve(output,mode+".png"),fullPage:true});
    console.log("Generated synthetic screen:",mode);
  }
  assert.deepEqual(blocked,[]);assert.deepEqual(errors,[]);
}finally{
  if(browser)await browser.close();
  await new Promise(done=>server.close(done));
}
