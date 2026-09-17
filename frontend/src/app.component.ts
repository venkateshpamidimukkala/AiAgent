import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';

interface Message { id:number; source:string; sender:string; subject:string; body:string; priority_score:number; priority_label:string; created_at:string; }
interface Draft { id:number; message_id:number; draft_text:string; status:string; }
interface MicrosoftStatus { configured:boolean; connected:boolean; account_email:string|null; unread_emails:number; upcoming_meetings:number; }
interface ConfluenceStatus { configured:boolean; connected:boolean; base_url:string; email:string; account_email?:string|null; }
interface ConfluencePage { title:string; space:string; updated:string|null; url:string; content:string; }
interface ConfluenceAnswer { answer:string; source:{title:string;url:string}; }
interface JiraStatus { configured:boolean; connected:boolean; base_url:string; email:string; account_email?:string|null; }
interface ConnectionStatus { database:{connected:boolean; type:string; name:string; schemas:string[]; tables:string[]; error:string|null}; providers:{microsoft:MicrosoftStatus; jira:JiraStatus; confluence:ConfluenceStatus}; }
interface ProviderStatusCard { key:'microsoft'|'jira'|'confluence'; label:string; status:MicrosoftStatus|JiraStatus|ConfluenceStatus; }
interface JiraIssue { key:string; summary:string; status:string; priority:string; assignee:string; updated:string|null; url:string; }
interface AssistantAnswer { id:number; query:string; answer:string; request_type:string; status:string; created_at:string; }
interface AssistantRequestRecord { id:number; request_text:string; request_type:string; response_text:string|null; status:string; created_at:string; }

@Component({selector:'app-root', standalone:true, imports:[CommonModule, FormsModule], templateUrl:'./app.component.html'})
export class AppComponent implements OnInit, OnDestroy {
  private http = inject(HttpClient);
  messages: Message[]=[]; selected?: Message; draft?: Draft;
  instruction='Reply as Venkat: I received your message and will review it and follow up today.'; revision=''; listening=false; status='';
  microsoftConnected=false; microsoftConfigured=false; microsoftEmail=''; microsoftUnread=0; microsoftMeetings=0; voiceEnabled=false; syncing=false;
  confluenceConnected=false; confluenceConfigured=false; confluenceUrl=''; confluenceEmail=''; confluenceToken=''; confluenceLink=''; confluenceQuestion=''; confluencePage?:ConfluencePage; confluenceAnswer?:ConfluenceAnswer; confluenceLoading=false;
  jiraConnected=false; jiraConfigured=false; jiraUrl=''; jiraEmail=''; jiraToken=''; jiraQuery=''; jiraIssues:JiraIssue[]=[]; jiraLoading=false;
  inboxSource='all'; jiraCommentIssue?:JiraIssue; jiraComment='';
  voiceStyle='natural'; preferredLanguage='en-US'; inputLanguage='en-US'; outputVoiceName=''; voiceSpeed=1; speaking=false; availableVoices:SpeechSynthesisVoice[]=[];
  loggedIn=false; setupComplete=false; showRegistration=false; navOpen=false; sidebarCollapsed=false; profileMenuOpen=false; accountView=''; profileName=''; profileEmail=''; profilePassword=''; newPassword=''; confirmNewPassword=''; loginEmail=''; loginName=''; registerName=''; registerEmail=''; registerPassword=''; registerConfirmPassword=''; selectedApps:string[]=[]; setupStep=1;
  currentTime=''; private clockTimer?: ReturnType<typeof setInterval>;
  activeNav='dashboard'; assistantLoading=false; assistantAnswer?:AssistantAnswer; assistantHistory:AssistantAnswer[]=[];
  searchOpen=false;
  connectionStatus?:ConnectionStatus; connectionsLoading=false;
  providerStatusCards:ProviderStatusCard[]=[
    {key:'microsoft',label:'Outlook',status:{configured:false,connected:false,account_email:null,unread_emails:0,upcoming_meetings:0}},
    {key:'microsoft',label:'Teams',status:{configured:false,connected:false,account_email:null,unread_emails:0,upcoming_meetings:0}},
    {key:'jira',label:'Jira',status:{configured:false,connected:false,base_url:'',email:''}},
    {key:'confluence',label:'Confluence',status:{configured:false,connected:false,base_url:'',email:''}}
  ];
  private knownMicrosoftIds = new Set<number>();

  ngOnInit(){
    this.updateCurrentTime();
    this.clockTimer=setInterval(()=>this.updateCurrentTime(),1000);
    this.loggedIn=localStorage.getItem('orbit-logged-in')==='true';
    this.setupComplete=localStorage.getItem('orbit-setup-complete')==='true';
    this.loginEmail=localStorage.getItem('orbit-email')||'';
    this.loginName=localStorage.getItem('orbit-name')||'';
    this.selectedApps=JSON.parse(localStorage.getItem('orbit-apps')||'[]');
    this.voiceEnabled=localStorage.getItem('voice-enabled')==='true';
    this.voiceStyle=localStorage.getItem('voice-style')||'natural';
    this.preferredLanguage=localStorage.getItem('voice-language')||'en-US';
    this.inputLanguage=localStorage.getItem('voice-input-language')||this.preferredLanguage;
    this.outputVoiceName=localStorage.getItem('voice-output')||'';
    this.voiceSpeed=Number(localStorage.getItem('voice-speed')||'1');
    this.sidebarCollapsed=localStorage.getItem('orbit-sidebar-collapsed')==='true';
    this.loadConnectionStatus();
    if('speechSynthesis' in window){this.availableVoices=speechSynthesis.getVoices();speechSynthesis.onvoiceschanged=()=>this.availableVoices=speechSynthesis.getVoices();}
    this.load(false);
    this.microsoftStatus();
    this.confluenceStatus();
    this.jiraStatus();
    this.loadAssistantHistory();
    if (new URLSearchParams(location.search).get('connected')==='microsoft') this.status='Microsoft Outlook and Teams connected';
  }

  ngOnDestroy(){if(this.clockTimer)clearInterval(this.clockTimer);}
  private updateCurrentTime(){this.currentTime=new Intl.DateTimeFormat(undefined,{hour:'numeric',minute:'2-digit',second:'2-digit'}).format(new Date());}

  load(readNew:boolean){
    this.http.get<Message[]>('/api/messages').subscribe({next:v=>{
      const newItems=v.filter(item=>item.source==='outlook'||item.source==='teams').filter(item=>!this.knownMicrosoftIds.has(item.id));
      this.messages=v;
      v.filter(item=>item.source==='outlook'||item.source==='teams').forEach(item=>this.knownMicrosoftIds.add(item.id));
      if(readNew && this.voiceEnabled && newItems.length) this.speakMessages(newItems);
    },error:()=>this.status='Backend unavailable'});
  }

  microsoftStatus(){this.http.get<MicrosoftStatus>('/api/auth/microsoft/status').subscribe(v=>{
    this.microsoftConfigured=v.configured; this.microsoftConnected=v.connected; this.microsoftEmail=v.account_email||''; this.microsoftUnread=v.unread_emails||0; this.microsoftMeetings=v.upcoming_meetings||0;
    if(v.connected) this.syncMessages(false);
  });}

  syncMessages(readNew=true){
    if(!this.microsoftConnected||this.syncing)return;
    this.syncing=true; this.status='Reading Outlook and Teams…';
    this.http.post<{status:string;counts:{outlook:number;teams:number}}>('/api/messages/sync',{}).subscribe({
      next:v=>{this.syncing=false;this.status=`Synced ${v.counts.outlook} Outlook and ${v.counts.teams} Teams messages`;this.load(readNew);},
      error:err=>{this.syncing=false;this.status=err.status===502?err.error?.detail||'Microsoft Graph sync failed':'Unable to sync Microsoft messages';}
    });
  }

  enableVoice(){
    this.voiceEnabled=true; localStorage.setItem('voice-enabled','true');
    this.status='Voice enabled. New Outlook and Teams messages will be read aloud.';
    if(this.messages.length) this.speakAssistant('Voice assistant is enabled. I will read your work messages and documentation aloud.');
  }

  disableVoice(){
    this.voiceEnabled=false; localStorage.setItem('voice-enabled','false'); this.stopSpeaking();
    this.status='Voice disabled. You can enable it again from Voice Settings.';
  }

  toggleNav(item:string){this.activeNav=this.activeNav===item?'dashboard':item;this.navOpen=false;}
  newConversation(){this.activeNav='dashboard';this.instruction='';this.assistantAnswer=undefined;this.assistantLoading=false;this.navOpen=false;}
  toggleSidebar(){this.sidebarCollapsed=!this.sidebarCollapsed;localStorage.setItem('orbit-sidebar-collapsed',String(this.sidebarCollapsed));}
  toggleProfileMenu(){this.profileMenuOpen=!this.profileMenuOpen;}
  openAccountView(view:string){this.profileMenuOpen=false;this.accountView=view;this.profileName=this.loginName;this.profileEmail=this.loginEmail;}
  saveProfile(){const name=this.profileName.trim();const email=this.profileEmail.trim();if(!name||!email){this.status='Enter your name and email.';return;}this.loginName=name;this.loginEmail=email;localStorage.setItem('orbit-name',name);localStorage.setItem('orbit-email',email);const user=JSON.parse(localStorage.getItem('orbit-user')||'{}');localStorage.setItem('orbit-user',JSON.stringify({...user,name,email}));this.accountView='';this.status='Profile updated successfully.';}
  changePassword(){if(!this.newPassword||this.newPassword.length<8){this.status='New password must be at least 8 characters.';return;}if(this.newPassword!==this.confirmNewPassword){this.status='Passwords do not match.';return;}const user=JSON.parse(localStorage.getItem('orbit-user')||'{}');localStorage.setItem('orbit-user',JSON.stringify({...user,password:this.newPassword}));this.newPassword='';this.confirmNewPassword='';this.accountView='';this.status='Password changed successfully.';}
  login(){if(!this.loginEmail.trim()||!this.loginName.trim()){this.status='Enter your name and email to continue.';return;}this.loggedIn=true;this.setupComplete=localStorage.getItem('orbit-setup-complete')==='true';localStorage.setItem('orbit-logged-in','true');localStorage.setItem('orbit-email',this.loginEmail.trim());localStorage.setItem('orbit-name',this.loginName.trim());}
  register(){const name=this.registerName.trim();const email=this.registerEmail.trim();if(!name||!email||!this.registerPassword){this.status='Complete all registration fields.';return;}if(this.registerPassword.length<8){this.status='Password must be at least 8 characters.';return;}if(this.registerPassword!==this.registerConfirmPassword){this.status='Passwords do not match.';return;}localStorage.setItem('orbit-user',JSON.stringify({name,email,password:this.registerPassword}));this.loginName=name;this.loginEmail=email;this.registerPassword='';this.registerConfirmPassword='';this.showRegistration=false;this.status='Registration complete. Sign in to continue.';}
  logout(){this.loggedIn=false;localStorage.removeItem('orbit-logged-in');this.stopSpeaking();}
  toggleSubscription(app:string){this.selectedApps=this.selectedApps.includes(app)?this.selectedApps.filter(item=>item!==app):[...this.selectedApps,app];}
  finishSetup(){if(!this.selectedApps.length){this.status='Select at least one app to continue.';return;}localStorage.setItem('orbit-apps',JSON.stringify(this.selectedApps));localStorage.setItem('orbit-setup-complete','true');this.setupComplete=true;this.status='Setup saved. Connect each selected app when you are ready.';}
  openConfluence(){
    this.activeNav='confluence';
    setTimeout(()=>document.getElementById('confluence-panel')?.scrollIntoView({behavior:'smooth',block:'start'}));
    if(!this.confluenceConnected)this.status='Connect Confluence with your site URL, email, and API token.';
  }
  openJira(){this.activeNav='jira';setTimeout(()=>document.getElementById('jira-panel')?.scrollIntoView({behavior:'smooth',block:'start'}));if(!this.jiraConnected)this.status='Connect Jira with your site URL, email, and API token.';}
  runAssistantQuery(query=this.instruction){
    const value=query.trim();
    if(!value||this.assistantLoading)return;
    this.instruction=value; this.assistantLoading=true; this.assistantAnswer=undefined; this.status='Orbit is searching your workspace…';
    this.http.post<AssistantAnswer>('/api/assistant/query',{query:value,request_type:'workspace'}).subscribe({
      next:answer=>{this.assistantAnswer=answer;this.assistantHistory=[answer,...this.assistantHistory.filter(item=>item.id!==answer.id)].slice(0,20);this.assistantLoading=false;this.status='Response generated and saved to PostgreSQL';if(this.voiceEnabled)this.speakAssistant(answer.answer);},
      error:err=>{this.assistantLoading=false;this.status=err.error?.detail||'Unable to reach the assistant service. Your request may not have been completed.';}
    });
  }
  loadAssistantHistory(){this.http.get<AssistantRequestRecord[]>('/api/assistant/requests?limit=20').subscribe({next:items=>this.assistantHistory=items.filter(item=>item.status==='completed').map(item=>({id:item.id,query:item.request_text,answer:item.response_text||'',request_type:item.request_type,status:item.status,created_at:item.created_at}))});}
  openConfluenceSettings(){this.activeNav='apps';this.status='Enter your Confluence details below.';}

  setInputLanguage(language:string){this.inputLanguage=language;localStorage.setItem('voice-input-language',language);}
  setOutputVoice(name:string){this.outputVoiceName=name;localStorage.setItem('voice-output',name);}
  outputVoiceOptions(){return this.availableVoices.filter(voice=>voice.lang.toLowerCase().startsWith(this.preferredLanguage.split('-')[0].toLowerCase()));}

  speakMessages(items:Message[]){
    const text=items.slice(0,5).map(item=>`${this.sourceName(item.source)} from ${item.sender}. Subject: ${item.subject}. ${item.body}`).join(' ');
    this.speakAssistant(text);
  }

  connectMicrosoft(){location.href='/api/auth/microsoft/login';}
  disconnectMicrosoft(){this.http.post('/api/auth/microsoft/disconnect',{}).subscribe(()=>{this.microsoftConnected=false;this.microsoftEmail='';this.status='Microsoft disconnected';});}
  select(item:Message){this.selected=item;this.draft=undefined;this.instruction=`Reply as Venkat: I received your message and will review it and follow up today.`;if(this.voiceEnabled)this.speakAssistant(`Venkat, you got a ${this.sourceName(item.source)} from ${item.sender}. Would you like me to prepare a reply?`);}
  createDraft(){if(!this.selected)return;this.http.post<Draft>('/api/replies/draft',{message_id:this.selected.id,instruction:this.instruction}).subscribe(v=>this.draft=v);}
  revise(){if(!this.draft)return;this.http.post<Draft>(`/api/replies/${this.draft.id}/revise`,{instruction:this.revision}).subscribe(v=>{this.draft=v;this.revision='';});}
  send(){if(!this.draft)return;this.http.post<{status:string}>(`/api/replies/${this.draft.id}/send`,{}).subscribe(v=>{this.status=v.status==='sent'?'Reply sent successfully':'Send failed';this.draft=undefined;});}
  sourceName(source:string){return source==='teams'?'Teams message':source==='outlook'?'Outlook email':source==='jira'?'Jira update':source==='confluence'?'Confluence page':`${source} notification`;}
  providerEmail(status:ProviderStatusCard['status']){return 'email' in status ? status.email : '';}
  providerUrl(status:ProviderStatusCard['status']){return 'base_url' in status ? status.base_url : '';}
  speak(text:string){this.speakAssistant(text);}
  speakAssistant(text:string){if(!('speechSynthesis' in window)){this.status='Text-to-speech is not supported in this browser';return;}this.speaking=true;this.http.post<{text:string}>('/api/voice/translate',{text,language:this.preferredLanguage}).subscribe({next:v=>this.playSpeech(v.text),error:()=>this.playSpeech(text)});}
  playSpeech(text:string){speechSynthesis.cancel();const utterance=new SpeechSynthesisUtterance(text);utterance.lang=this.preferredLanguage;const voices=this.availableVoices.length?this.availableVoices:speechSynthesis.getVoices();const languageCode=this.preferredLanguage.split('-')[0];const languageVoice=voices.filter(v=>v.lang.toLowerCase().startsWith(languageCode));const selected=voices.find(v=>v.name===this.outputVoiceName);const female=languageVoice.find(v=>/female|samantha|zira|karen|victoria|google.*female/i.test(v.name));const male=languageVoice.find(v=>/male|david|alex|daniel|google.*male/i.test(v.name));utterance.voice=selected||(this.voiceStyle==='female'&&female)||(this.voiceStyle==='male'&&male)||languageVoice[0]||voices[0]||null;utterance.rate=this.voiceStyle==='siri'?1.01:0.94;utterance.pitch=this.voiceStyle==='female'?1.08:this.voiceStyle==='male'?0.88:1;utterance.onend=()=>this.speaking=false;utterance.onerror=()=>this.speaking=false;speechSynthesis.speak(utterance);}
  stopSpeaking(){if('speechSynthesis' in window){speechSynthesis.cancel();this.speaking=false;}}
  confluenceStatus(){this.http.get<ConfluenceStatus>('/api/confluence/status').subscribe({next:v=>{this.confluenceConfigured=v.configured;this.confluenceConnected=v.connected;this.confluenceUrl=v.base_url;this.confluenceEmail=v.email;this.providerStatusCards[3]={key:'confluence',label:'Confluence',status:v};},error:()=>this.status='Unable to read Confluence connection status'});}
  jiraStatus(){this.http.get<JiraStatus>('/api/jira/status').subscribe({next:v=>{this.jiraConfigured=v.configured;this.jiraConnected=v.connected;this.jiraUrl=v.base_url;this.jiraEmail=v.email;this.providerStatusCards[2]={key:'jira',label:'Jira',status:v};},error:()=>this.status='Unable to read Jira connection status'});}
  loadConnectionStatus(){this.connectionsLoading=true;this.http.get<ConnectionStatus>('/api/connections/status').subscribe({next:v=>{this.connectionStatus=v;this.setProviderStatusCards(v.providers);this.connectionsLoading=false;},error:()=>{this.connectionsLoading=false;this.status='Unable to read combined connection status. Showing individual provider statuses.';this.jiraStatus();this.confluenceStatus();}});}
  setProviderStatusCards(providers:ConnectionStatus['providers']){this.providerStatusCards=[{key:'microsoft',label:'Outlook',status:providers.microsoft},{key:'microsoft',label:'Teams',status:providers.microsoft},{key:'jira',label:'Jira',status:providers.jira},{key:'confluence',label:'Confluence',status:providers.confluence}];this.microsoftConfigured=providers.microsoft.configured;this.microsoftConnected=providers.microsoft.connected;this.microsoftEmail=providers.microsoft.account_email||'';this.jiraConfigured=providers.jira.configured;this.jiraConnected=providers.jira.connected;this.jiraUrl=providers.jira.base_url;this.jiraEmail=providers.jira.email;this.confluenceConfigured=providers.confluence.configured;this.confluenceConnected=providers.confluence.connected;this.confluenceUrl=providers.confluence.base_url;this.confluenceEmail=providers.confluence.email;}
  openConnections(){this.activeNav='connections';this.loadConnectionStatus();}
  connectJira(){this.jiraUrl=this.jiraUrl.trim().replace(/\/$/,'');this.jiraEmail=this.jiraEmail.trim();this.jiraToken=this.jiraToken.trim();if(!this.jiraUrl||!this.jiraEmail||!this.jiraToken){this.status='Enter the Jira site URL, email, and API token.';return;}this.status='Connecting to Jira…';this.http.post<JiraStatus>('/api/jira/connect',{base_url:this.jiraUrl,email:this.jiraEmail,api_token:this.jiraToken}).subscribe({next:v=>{this.jiraConfigured=v.configured;this.jiraConnected=v.connected;this.jiraToken='';this.providerStatusCards[2]={key:'jira',label:'Jira',status:v};this.status='Jira connected. Search your accessible issues.';},error:e=>this.status=e.error?.detail||'Unable to connect Jira'});}
  disconnectJira(){this.http.post('/api/jira/disconnect',{}).subscribe({next:()=>{this.jiraConnected=false;this.jiraConfigured=false;this.jiraIssues=[];this.status='Jira disconnected';},error:()=>this.status='Unable to disconnect Jira'});}
  searchJira(){const query=this.jiraQuery.trim();if(!query){this.status='Enter a Jira issue search.';return;}if(!this.jiraConnected){this.status='Connect Jira before searching issues.';return;}this.jiraLoading=true;this.http.post<{issues:JiraIssue[]}>('/api/jira/search',{query}).subscribe({next:v=>{this.jiraIssues=v.issues;this.jiraLoading=false;this.status=v.issues.length?`Found ${v.issues.length} Jira issues`:'No matching Jira issues found';},error:e=>{this.jiraLoading=false;this.status=e.error?.detail||'Unable to search Jira';}});}
  prepareJiraComment(issue:JiraIssue){this.jiraCommentIssue=issue;this.jiraComment=`Hi, this is Venkat. I reviewed ${issue.key} and will add an update shortly.`;this.status=`Draft comment ready for ${issue.key}. Review it, then choose “Yes, add comment”.`;
    if(this.voiceEnabled)this.speakAssistant(`Venkat, I am not seeing your comment on ${issue.key}. I prepared a comment. Do you want me to add it?`);
  }
  addJiraComment(){if(!this.jiraCommentIssue||!this.jiraComment.trim())return;this.http.post<{status:string}>('/api/jira/comment',{issue_key:this.jiraCommentIssue.key,body:this.jiraComment.trim()}).subscribe({next:()=>{this.status=`Comment added to ${this.jiraCommentIssue?.key}`;this.jiraCommentIssue=undefined;this.jiraComment='';},error:e=>this.status=e.error?.detail||'Unable to add Jira comment'});}
  connectConfluence(){
    this.confluenceUrl=this.confluenceUrl.trim().replace(/\/$/,'');
    this.confluenceEmail=this.confluenceEmail.trim();
    this.confluenceToken=this.confluenceToken.trim();
    if(!this.confluenceUrl||!this.confluenceEmail||!this.confluenceToken){this.status='Enter the Confluence site URL, email, and API token.';return;}
    this.http.post<ConfluenceStatus>('/api/confluence/connect',{base_url:this.confluenceUrl,email:this.confluenceEmail,api_token:this.confluenceToken}).subscribe({next:v=>{this.confluenceConfigured=v.configured;this.confluenceConnected=v.connected;this.confluenceToken='';this.providerStatusCards[3]={key:'confluence',label:'Confluence',status:v};this.status='Confluence connected. Paste a page link to search it.';},error:e=>this.status=e.error?.detail||'Unable to connect Confluence'});
  }
  disconnectConfluence(){this.http.post('/api/confluence/disconnect',{}).subscribe(()=>{this.confluenceConnected=false;this.confluenceConfigured=false;this.status='Confluence disconnected';});}
  loadConfluence(){
    if(!this.confluenceLink.trim())return;
    if(!/\/pages\/\d+|pageId=\d+|^\d+$/.test(this.confluenceLink.trim())){this.confluenceQuestion=this.confluenceLink;this.askConfluence(this.confluenceLink);return;}
    this.confluenceLoading=true;this.confluenceAnswer=undefined;this.http.post<ConfluencePage>('/api/confluence/page',{url:this.confluenceLink}).subscribe({next:v=>{this.confluencePage=v;this.confluenceLoading=false;this.status='Confluence page loaded. Ask a question about it.';},error:e=>{this.confluenceLoading=false;this.status=e.error?.detail||'Unable to load Confluence page';}});
  }
  askConfluence(question=this.confluenceQuestion){
    if(!this.confluenceLink.trim()&&this.confluencePage?.url)this.confluenceLink=this.confluencePage.url;
    if(!question.trim()){this.status='Enter a question for Confluence.';return;}
    this.confluenceQuestion=question;this.confluenceLoading=true;this.confluenceAnswer=undefined;
    const pageUrl=/\/pages\/\d+|pageId=\d+|^\d+$/.test(this.confluenceLink.trim())?this.confluenceLink.trim():'';
    this.http.post<ConfluenceAnswer>('/api/confluence/ask',{url:pageUrl,question}).subscribe({next:v=>{this.confluenceAnswer=v;this.confluenceLoading=false;this.status='Answer generated from Confluence';if(this.voiceEnabled)this.speakAssistant(v.answer);},error:e=>{this.confluenceLoading=false;this.status=e.error?.detail||'Unable to answer from Confluence';}});
  }
  setVoiceStyle(style:string){this.voiceStyle=style;localStorage.setItem('voice-style',style);}
  setPreferredLanguage(language:string){this.preferredLanguage=language;localStorage.setItem('voice-language',language);}
  setVoiceSpeed(speed:number){this.voiceSpeed=Number(speed);localStorage.setItem('voice-speed',String(this.voiceSpeed));}
  speakWithStyle(text:string){this.speakAssistant(text);}
  listen(){const Recognition=(window as any).SpeechRecognition||(window as any).webkitSpeechRecognition;if(!Recognition){this.status='Speech recognition is not supported in this browser';return;}const r=new Recognition();r.lang=this.inputLanguage;this.listening=true;r.onresult=(e:any)=>{const text=e.results[0][0].transcript;const yes=/^(yes|yeah|yep|send it|add it|do it)\b/i.test(text.trim());if(yes&&this.draft)this.send();else if(yes&&this.jiraCommentIssue)this.addJiraComment();else if(this.confluencePage||this.confluenceLink){this.confluenceQuestion=text;this.askConfluence(text);}else this.instruction=text;this.listening=false;};r.onerror=()=>this.listening=false;r.onend=()=>this.listening=false;r.start();}
}