#!/usr/bin/env node
/* Build the client-facing .docx.
 *
 * Split of responsibility: this script owns the Word mechanics (page size, table
 * widths, shading, image embedding) which are fiddly and already debugged. The
 * WORDS come from a narrative JSON the model writes — judgement belongs there,
 * not in a template. Numbers always come from the data blob so the prose and the
 * tables cannot drift apart.
 *
 *   node build_docx.js --data r.json --narrative n.json --charts ./charts --out report.docx
 *
 * Requires `npm install docx` IN THE WORKING DIRECTORY (require resolves from cwd).
 */
const fs=require("fs"), path=require("path");
/* Resolve `docx` from the skill directory first (it ships installed there), then
 * from the current working directory. Node resolves requires relative to THIS
 * file, not the cwd, so "npm install docx" in an output folder does not help. */
function loadDocx(){
  for (const base of [path.join(__dirname,".."), process.cwd()]) {
    try { return require(require.resolve("docx",{paths:[base]})); } catch(e){}
  }
  try { return require("docx"); } catch(e){
    console.error("Cannot find the 'docx' package. Run:  npm install docx  inside "+path.join(__dirname,".."));
    process.exit(1);
  }
}
const {Document,Packer,Paragraph,TextRun,HeadingLevel,AlignmentType,Table,TableRow,TableCell,
WidthType,ShadingType,BorderStyle,ImageRun,PageBreak,LevelFormat,convertInchesToTwip}=loadDocx();

const arg=k=>{const i=process.argv.indexOf(k);return i>0?process.argv[i+1]:null;};
const D=JSON.parse(fs.readFileSync(arg("--data"),"utf8"));
const N=JSON.parse(fs.readFileSync(arg("--narrative"),"utf8"));
const CH=arg("--charts")||".", OUT=arg("--out")||"report.docx";
const ACCENT=(N.accent||"E31A1C").replace("#",""), DARK="1F2430", GREY="6B7280",
      LIGHT="F3F4F7", GREEN="1B8A5A", LINE="D6D9E3", TXT="333845";
const money=v=>v==null?"—":"$"+Number(v).toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2});
const num=v=>Number(v).toLocaleString("en-US");
const has=f=>fs.existsSync(path.join(CH,f));

const gap=(n=140)=>new Paragraph({spacing:{after:n},children:[]});
const h1=t=>new Paragraph({heading:HeadingLevel.HEADING_1,spacing:{before:320,after:140},
  children:[new TextRun({text:t,bold:true,size:30,color:DARK})]});
const h2=t=>new Paragraph({heading:HeadingLevel.HEADING_2,spacing:{before:260,after:110},
  children:[new TextRun({text:t,bold:true,size:24,color:DARK})]});
const body=t=>new Paragraph({spacing:{after:140,line:300},children:[new TextRun({text:t,size:21,color:TXT})]});
const bullet=t=>new Paragraph({numbering:{reference:"dots",level:0},spacing:{after:90,line:290},
  children:[new TextRun({text:t,size:21,color:TXT})]});
const pic=(f,w,h)=>new Paragraph({alignment:AlignmentType.CENTER,spacing:{before:80,after:200},
  children:[new ImageRun({type:"png",data:fs.readFileSync(path.join(CH,f)),transformation:{width:w,height:h}})]});

const callout=(title,lines,accent)=>new Table({
  columnWidths:[9360],width:{size:9360,type:WidthType.DXA},
  borders:{top:{style:BorderStyle.SINGLE,size:2,color:"FFFFFF"},bottom:{style:BorderStyle.SINGLE,size:2,color:"FFFFFF"},
    left:{style:BorderStyle.SINGLE,size:18,color:accent||ACCENT},right:{style:BorderStyle.SINGLE,size:2,color:"FFFFFF"},
    insideHorizontal:{style:BorderStyle.NONE},insideVertical:{style:BorderStyle.NONE}},
  rows:[new TableRow({children:[new TableCell({width:{size:9360,type:WidthType.DXA},
    shading:{type:ShadingType.CLEAR,fill:LIGHT,color:"auto"},margins:{top:200,bottom:200,left:220,right:220},
    children:[new Paragraph({spacing:{after:90},children:[new TextRun({text:title,bold:true,size:22,color:DARK})]}),
      ...lines.map(l=>new Paragraph({spacing:{after:70},children:[new TextRun({text:l,size:20,color:TXT})]}))]})]})]});

const tbl=(head,rows,widths,boldLast)=>new Table({
  columnWidths:widths,width:{size:widths.reduce((a,b)=>a+b,0),type:WidthType.DXA},
  borders:{top:{style:BorderStyle.SINGLE,size:4,color:LINE},bottom:{style:BorderStyle.SINGLE,size:4,color:LINE},
    left:{style:BorderStyle.NONE},right:{style:BorderStyle.NONE},
    insideHorizontal:{style:BorderStyle.SINGLE,size:2,color:"EAECF2"},insideVertical:{style:BorderStyle.NONE}},
  rows:[new TableRow({tableHeader:true,children:head.map((c,i)=>new TableCell({
      width:{size:widths[i],type:WidthType.DXA},shading:{type:ShadingType.CLEAR,fill:DARK,color:"auto"},
      margins:{top:110,bottom:110,left:130,right:130},
      children:[new Paragraph({alignment:i?AlignmentType.CENTER:AlignmentType.LEFT,
        children:[new TextRun({text:String(c),bold:true,size:19,color:"FFFFFF"})]})]}))}),
    ...rows.map((r,ri)=>new TableRow({children:r.map((c,i)=>new TableCell({
      width:{size:widths[i],type:WidthType.DXA},
      shading:{type:ShadingType.CLEAR,fill:ri%2?"FAFBFC":"FFFFFF",color:"auto"},
      margins:{top:100,bottom:100,left:130,right:130},
      children:[new Paragraph({alignment:i?AlignmentType.CENTER:AlignmentType.LEFT,
        children:[new TextRun({text:String(c),size:19,
          bold:!!(boldLast&&i===r.length-1),color:(boldLast&&i===r.length-1)?GREEN:TXT})]})]}))}))]});

const kids=[];
// cover
kids.push(new Paragraph({spacing:{after:40},children:[new TextRun({text:(D.client||"").toUpperCase(),bold:true,size:17,color:ACCENT,characterSpacing:30})]}));
kids.push(new Paragraph({spacing:{after:60},border:{bottom:{style:BorderStyle.SINGLE,size:12,color:ACCENT}},
  children:[new TextRun({text:N.title||"Google Ads Report",bold:true,size:44,color:DARK})]}));
kids.push(new Paragraph({spacing:{before:120,after:280},children:[new TextRun({text:N.subtitle,size:19,color:GREY})]}));
kids.push(callout(N.standing.title||"Where things stand",N.standing.lines));
kids.push(gap(220));

// leads
if(N.sections.leads){
  kids.push(h1(N.sections.leads.heading||"Enquiries"));
  (N.sections.leads.paras||[]).forEach(p=>kids.push(body(p)));
  if(has("c1_leadrate.png")) kids.push(pic("c1_leadrate.png",612,264));
  (N.sections.leads.after_chart||[]).forEach(p=>kids.push(body(p)));
  if((N.sections.leads.table||[]).length){
    kids.push(h2(N.sections.leads.table_heading||"Who got in touch"));
    kids.push(tbl(N.sections.leads.table_head,N.sections.leads.table,N.sections.leads.table_widths||[2100,2900,2600,1760]));
    kids.push(gap(170));
  }
  (N.sections.leads.closing||[]).forEach(p=>kids.push(body(p)));
}
// cost
kids.push(new Paragraph({children:[new PageBreak()]}));
kids.push(h1(N.sections.cost.heading||"What it costs"));
if(has("c2_cpl.png")) kids.push(pic("c2_cpl.png",612,255));
(N.sections.cost.paras||[]).forEach(p=>kids.push(body(p)));
if(has("c4_spend.png")) kids.push(pic("c4_spend.png",612,221));
(N.sections.cost.after_spend||[]).forEach(p=>kids.push(body(p)));
// behaviour
if(N.sections.behaviour && has("c3_behaviour.png")){
  kids.push(h1(N.sections.behaviour.heading||"How visitors behave on your site"));
  (N.sections.behaviour.paras||[]).forEach(p=>kids.push(body(p)));
  kids.push(pic("c3_behaviour.png",612,246));
  (N.sections.behaviour.after_chart||[]).forEach(p=>kids.push(body(p)));
}
// changes + recommendations
kids.push(new Paragraph({children:[new PageBreak()]}));
if(N.sections.changes){ kids.push(h1(N.sections.changes.heading||"What we changed"));
  (N.sections.changes.bullets||[]).forEach(b=>kids.push(bullet(b))); }
if(N.sections.recommend){ kids.push(h1(N.sections.recommend.heading||"What we recommend next"));
  (N.sections.recommend.items||[]).forEach(it=>{kids.push(h2(it.heading)); (it.paras||[]).forEach(p=>kids.push(body(p)));}); }
if(N.sections.help) kids.push(callout(N.sections.help.title||"What would help us most",N.sections.help.lines,DARK));

// numbers
kids.push(new Paragraph({children:[new PageBreak()]}));
kids.push(h1("The numbers"));
kids.push(h2(N.numbers_heading||"Period by period"));
const W=D.windows, lbl=W.map(w=>w.label);
kids.push(tbl(["",...lbl,"Total"],[
  ["Times your ads were shown",...W.map(w=>num(w.impressions)),num(D.totals.impressions)],
  ["Visits to your site",...W.map(w=>num(w.clicks)),num(D.totals.clicks)],
  [N.lead_row_label||"Enquiries",...W.map(w=>String(Math.round(w.leads))),String(Math.round(D.totals.leads))],
  // secondary actions (e.g. direction requests for a walk-in venue) — shown, never blended into enquiries
  ...Object.keys(D.totals.secondary||{}).map(k=>[k,...W.map(w=>num(Math.round((w.secondary||{})[k]||0))),num(Math.round(D.totals.secondary[k]))]),
  [N.rate_row_label||"Enquiries per 100 visits",...W.map(w=>w.cvr.toFixed(2)+"%"),D.totals.cvr.toFixed(2)+"%"],
  ["Cost per visit",...W.map(w=>money(w.cpc)),money(D.totals.cpc)],
  [N.cost_row_label||"Cost per enquiry",...W.map(w=>money(w.cpl)),money(D.totals.cpl)],
  ["Average spend per day",...W.map(w=>money(w.per_day)),money(D.totals.per_day)],
  ["Total spent",...W.map(w=>money(w.cost)),money(D.totals.cost)]],
  [3100,...W.map(()=>Math.floor(4440/W.length)),1820]));
kids.push(gap(200));
if((N.service_table||[]).length){
  kids.push(h2(N.service_table_heading||"Where your money went"));
  kids.push(tbl(N.service_table_head||["Service","Times shown","Visits","Spent","Enquiries"],N.service_table,[3260,1500,1200,1500,1900],true));
}
// glossary
kids.push(h1("Plain English"));
(N.glossary||[]).forEach(([t,dsc])=>kids.push(new Paragraph({spacing:{after:110},children:[
  new TextRun({text:t+" — ",bold:true,size:20,color:DARK}),new TextRun({text:dsc,size:20,color:TXT})]})));
kids.push(gap(260));
kids.push(new Paragraph({border:{top:{style:BorderStyle.SINGLE,size:6,color:LINE}},spacing:{before:160,after:90},children:[]}));
(N.footer||[]).forEach((f,i)=>kids.push(new Paragraph({spacing:{after:60},
  children:[new TextRun({text:f,size:i?18:19,italics:i===0,color:GREY})]})));

const doc=new Document({creator:"MakeThisQuick",title:`${D.client} — Google Ads Report`,
  numbering:{config:[{reference:"dots",levels:[{level:0,format:LevelFormat.BULLET,text:"•",alignment:AlignmentType.LEFT,
    style:{paragraph:{indent:{left:convertInchesToTwip(0.3),hanging:convertInchesToTwip(0.18)}}}}]}]},
  sections:[{properties:{page:{size:{width:12240,height:15840},margin:{top:1080,bottom:1080,left:1440,right:1440}}},children:kids}]});
Packer.toBuffer(doc).then(b=>{fs.writeFileSync(OUT,b);console.log(JSON.stringify({written:OUT,bytes:b.length},null,1));});
