proj=args[0];
params = [:];
for (p in args[1].tokenize(";")){
  def x=p.tokenize("=");
  def v="";
  if (x[1]!=null){v=x[1];}
  params[x[0]]=v;
}
try {id2ignore=args[2].toInteger();}
catch ( e ) {id2ignore=0;}
println "Procject:"+proj;
println "Params:"+params
for (it in jenkins.model.Jenkins.instance.getItem(proj).builds)
{
  if (it.isInProgress() != true){continue;}
  if (it.getNumber() == id2ignore){continue;}
  println "  Checking job number: "+it.getNumber();
  def all_ok = true;
  for (p in params)
  { 
    def cv="";
    try {
      cv = it.getBuildVariables()[p.key];
      if (cv != p.value){all_ok=false;}
    }
    catch ( e ) {all_ok=false; println "    "+e;}
    if (all_ok){println "    Matched   : "+p;}
    else{println "    Unmatched : "+p+"("+cv+")"; break;}
  }
  if (all_ok==false){continue;}
  println "  Killing job "+proj+" "+it.getNumber()
  it.doStop();
}

