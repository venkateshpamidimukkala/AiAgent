import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';

interface Message { id:number; source:string; sender:string; subject:string; body:string; priority_score:number; priority_label:string; created_at:string; }
interface Draft { id:number; message_id:number; draft_text:string; status:string; }
interface MicrosoftStatus { configured:boolean; connected:boolean; account_email:string|null; unread_emails:number; upcoming_meetings:number; }
interface ConfluenceStatus { configured:boolean; connected:boolean; base_url:string; email:string; account_email?:string|null; }
interface ConfluencePage { title:string; space:string; updated:string|null; url:string; content:string; }
interface ConfluenceAnswer { answer:string; summary:string; key_points:string[]; problems:string[]; implementation:string[]; source:{title:string;url:string}; }
interface JiraStatus { configured:boolean; connected:boolean; base_url:string; email:string; account_email?:string|null; }
interface ConnectionStatus { database:{connected:boolean; type:string; name:string; schemas:string[]; tables:string[]; error:string|null}; providers:{microsoft:MicrosoftStatus; jira:JiraStatus; confluence:ConfluenceStatus}; }
interface ProviderStatusCard { key:'microsoft'|'jira'|'confluence'; label:string; status:MicrosoftStatus|JiraStatus|ConfluenceStatus; }
interface JiraIssue { key:string; summary:string; status:string; priority:string; assignee:string; updated:string|null; url:string; description?:string; sprint?:string; epic?:string; issue_type?:string; labels?:string[]; due_date?:string|null; story_points?:number|null; }
interface JiraComment { id:string; author:string; created:string|null; body:string; }
interface JiraDailyIssue extends JiraIssue { comment:string; }
interface AssistantAnswer { id:number; query:string; answer:string; request_type:string; status:string; created_at:string; }
interface AssistantRequestRecord { id:number; request_text:string; request_type:string; response_text:string|null; status:string; created_at:string; }

@Component({selector:'app-root', standalone:true, imports:[CommonModule, FormsModule], templateUrl:'./app.component.html'})
export class AppComponent implements OnInit, OnDestroy {
  private http = inject(HttpClient);
  private mockInboxStatusTimer?: ReturnType<typeof setTimeout>;
  private jiraStatusTimer?: ReturnType<typeof setTimeout>;
  messages: Message[]=[]; selected?: Message; draft?: Draft;
  instruction='I received your message and will review it and follow up today.'; revision=''; listening=false; status='';
  microsoftConnected=false; microsoftConfigured=false; microsoftEmail=''; microsoftUnread=0; microsoftMeetings=0; voiceEnabled=false; syncing=false;
  confluenceConnected=false; confluenceConfigured=false; confluenceUrl=''; confluenceEmail=''; confluenceToken=''; confluenceLink=''; confluenceSourceLink=''; confluenceQuestion=''; confluenceFocus='everything'; confluencePage?:ConfluencePage; confluenceAnswer?:ConfluenceAnswer; confluenceLoading=false;
  jiraConnected=false; jiraConfigured=false; jiraUrl=''; jiraEmail=''; jiraToken=''; jiraQuery='KAN-1'; jiraBoard=''; jiraIssues:JiraIssue[]=[]; jiraLoading=false; jiraSyncing=false; jiraLastSynced=''; jiraSelectedIssue?:JiraIssue; jiraStatusFilter='All'; jiraPriorityFilter='All'; jiraAssigneeFilter='All'; jiraSprintFilter='All'; jiraEpicFilter='All'; jiraTypeFilter='All'; jiraSort='updated'; jiraSortDescending=true; jiraPage=1; jiraPageSize=10; jiraSelectedKeys=new Set<string>();
  inboxSource='all'; draftText=''; jiraCommentIssue?:JiraIssue; jiraComment=''; jiraComments:JiraComment[]=[]; jiraReplyTo?:JiraComment; jiraCommentsLoading=false; jiraCommentSubmitting=false;
  jiraDailyIssues:JiraDailyIssue[]=[]; jiraDailyLoading=false;
  jiraVoiceState:'idle'|'listening'|'processing'|'ready'|'posted'='idle'; jiraVoiceTranscript=''; jiraVoiceDraft=''; jiraVoiceError=''; jiraVoiceDuration=0; jiraVoicePostedAt?:Date; jiraVoicePostedPreview=''; jiraAiSuggestion=''; jiraImproveOpen=false; jiraImproveOptions=['Professional','Shorten','Expand','Rephrase','Formal','Friendly']; private jiraVoiceRecognition:any; private jiraVoiceFinalTranscript=''; private jiraVoiceTimer?:ReturnType<typeof setInterval>;
  voiceStyle='natural'; preferredLanguage='en-US'; inputLanguage='en-US'; outputVoiceName=''; voiceSpeed=1; speaking=false; availableVoices:SpeechSynthesisVoice[]=[];
  loggedIn=false; setupComplete=false; showRegistration=false; navOpen=false; sidebarCollapsed=false; profileMenuOpen=false; accountView=''; profileName=''; profileEmail=''; profilePassword=''; newPassword=''; confirmNewPassword=''; loginEmail=''; loginName=''; registerName=''; registerEmail=''; registerPassword=''; registerConfirmPassword=''; selectedApps:string[]=[]; setupStep=1;
  currentTime=''; greeting='Good morning'; private clockTimer?: ReturnType<typeof setInterval>; private jiraSyncTimer?: ReturnType<typeof setInterval>; private voicesChangedHandler?:()=>void;
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

  get currentUserName(){return this.loginName.trim()||'there';}

  ngOnInit(){
    this.initializeSpeech();
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
    this.load(false);
    this.microsoftStatus();
    this.confluenceStatus();
    this.jiraStatus();
    this.loadAssistantHistory();
    const microsoftParams=new URLSearchParams(location.search);
    if(microsoftParams.get('connected')==='microsoft'){
      const microsoftError=microsoftParams.get('error_description')||microsoftParams.get('error');
      this.status=microsoftError?`Microsoft authorization failed: ${microsoftError}`:'Microsoft Outlook and Teams connected';
    }
  }

  ngOnDestroy(){if(this.clockTimer)clearInterval(this.clockTimer);if(this.jiraSyncTimer)clearInterval(this.jiraSyncTimer);if(this.mockInboxStatusTimer)clearTimeout(this.mockInboxStatusTimer);if(this.voicesChangedHandler&&'speechSynthesis' in window)speechSynthesis.removeEventListener('voiceschanged',this.voicesChangedHandler);this.stopSpeaking();}
  private initializeSpeech(){
    if(!('speechSynthesis' in window))return;
    const loadVoices=()=>{this.availableVoices=window.speechSynthesis.getVoices();};
    loadVoices();
    this.voicesChangedHandler=loadVoices;
    window.speechSynthesis.addEventListener('voiceschanged',loadVoices);
  }
  private updateCurrentTime(){const now=new Date(); this.currentTime=new Intl.DateTimeFormat(undefined,{hour:'numeric',minute:'2-digit',second:'2-digit'}).format(now); const hour=now.getHours(); this.greeting=hour<12?'Good morning':hour<18?'Good afternoon':'Good evening';}

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
  openJira(){this.activeNav='jira';setTimeout(()=>document.getElementById('jira-panel')?.scrollIntoView({behavior:'smooth',block:'start'}));if(this.jiraConnected){this.startJiraSync();if(!this.jiraIssues.length)this.loadJiraIssue('KAN-1');}else this.status='Connect Jira with your site URL, email, and API token.';}
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

  openMockInbox(source:'outlook'|'teams'){
    this.activeNav='inbox';
    this.inboxSource=source;
    this.navOpen=false;
    this.selected=undefined;
    this.draft=undefined;
    const mockInboxStatus=`Showing mock ${source === 'outlook' ? 'Outlook' : 'Teams'} messages.`;
    this.status=mockInboxStatus;
    if(this.mockInboxStatusTimer)clearTimeout(this.mockInboxStatusTimer);
    this.mockInboxStatusTimer=setTimeout(()=>{if(this.status===mockInboxStatus)this.status='';},5000);
  }

  setInputLanguage(language:string){this.inputLanguage=language;localStorage.setItem('voice-input-language',language);}
  setOutputVoice(name:string){this.outputVoiceName=name;localStorage.setItem('voice-output',name);}
  outputVoiceOptions(){return this.availableVoices.filter(voice=>voice.lang.toLowerCase().startsWith(this.preferredLanguage.split('-')[0].toLowerCase()));}

  speakMessages(items:Message[]){
    const text=items.slice(0,5).map(item=>`${this.sourceName(item.source)} from ${item.sender}. Subject: ${item.subject}. ${item.body}`).join(' ');
    this.speakAssistant(text);
  }

  connectMicrosoft(){location.href='/api/auth/microsoft/login';}
  disconnectMicrosoft(){this.http.post('/api/auth/microsoft/disconnect',{}).subscribe(()=>{this.microsoftConnected=false;this.microsoftEmail='';this.status='Microsoft disconnected';});}
  select(item:Message){this.selected=item;this.draft=undefined;this.instruction=`Reply as ${this.currentUserName}: I received your message and will review it and follow up today.`;if(this.voiceEnabled)this.speakAssistant(`${this.currentUserName}, you got a ${this.sourceName(item.source)} from ${item.sender}. Would you like me to prepare a reply?`);}
  createDraft(){if(!this.selected)return;this.http.post<Draft>('/api/replies/draft',{message_id:this.selected.id,instruction:this.instruction}).subscribe(v=>{this.draft=v;this.draftText=v.draft_text;});}
  revise(){if(!this.draft)return;this.http.post<Draft>(`/api/replies/${this.draft.id}/revise`,{instruction:this.revision||this.draftText}).subscribe(v=>{this.draft=v;this.draftText=v.draft_text;this.revision='';});}
  send(){if(!this.draft)return;this.http.post<{status:string}>(`/api/replies/${this.draft.id}/send`,{}).subscribe(v=>{this.status=v.status==='sent'?'Reply sent successfully':'Send failed';this.draft=undefined;this.draftText='';});}
  get teamsMessageCount(){return this.messages.filter(item=>item.source==='teams').length;}
  get outlookMessageCount(){return this.messages.filter(item=>item.source==='outlook').length;}
  get pendingReplyCount(){return this.messages.filter(item=>item.source==='teams'||item.source==='outlook').filter(item=>item.id!==this.draft?.message_id).length;}
  get aiDraftCount(){return this.draft ? 1 : Math.min(5,Math.max(1,this.messages.length));}
  avatarInitials(sender:string){return sender.split(/\s+/).map(part=>part[0]).join('').slice(0,2).toUpperCase();}
  messageAge(value:string){const date=new Date(value);if(Number.isNaN(date.getTime()))return 'New';const minutes=Math.max(1,Math.round((Date.now()-date.getTime())/60000));return minutes<60?`${minutes} min ago`:`${Math.round(minutes/60)} hr ago`;}
  generateCommunicationReply(){if(!this.selected)return;this.instruction='Write a concise, professional reply that acknowledges the message, addresses the request, and confirms the next step.';this.createDraft();}
  focusReplyBox(){document.querySelector<HTMLElement>('.reply-block textarea')?.focus();}
  sourceName(source:string){return source==='teams'?'Teams message':source==='outlook'?'Outlook email':source==='jira'?'Jira update':source==='confluence'?'Confluence page':`${source} notification`;}
  providerEmail(status:ProviderStatusCard['status']){return 'email' in status ? status.email : '';}
  providerUrl(status:ProviderStatusCard['status']){return 'base_url' in status ? status.base_url : '';}
  speak(text:string){this.speakAssistant(text);}
  speakAssistant(text:string){
    if(!('speechSynthesis' in window)){this.status='Text-to-speech is not supported in this browser';return;}
    const source=text.trim();
    if(!source){this.status='There is no text to read aloud';return;}
    this.speaking=true;
    this.http.post<{text:string}>('/api/voice/translate',{text:source,language:this.preferredLanguage}).subscribe({
      next:v=>this.playSpeech((v?.text||source).trim()),
      error:()=>this.playSpeech(source)
    });
  }
  playSpeech(text:string){
    const synth=window.speechSynthesis;
    if(!text.trim()){this.speaking=false;return;}
    synth.cancel();
    const utterance=new SpeechSynthesisUtterance(text);
    utterance.lang=this.preferredLanguage;
    const voices=this.availableVoices.length?this.availableVoices:synth.getVoices();
    const languageCode=this.preferredLanguage.split('-')[0].toLowerCase();
    const languageVoice=voices.filter(v=>v.lang.toLowerCase().startsWith(languageCode));
    const selected=voices.find(v=>v.name===this.outputVoiceName);
    const female=languageVoice.find(v=>/female|samantha|zira|karen|victoria|google.*female/i.test(v.name));
    const male=languageVoice.find(v=>/male|david|alex|daniel|google.*male/i.test(v.name));
    utterance.voice=selected||(this.voiceStyle==='female'&&female)||(this.voiceStyle==='male'&&male)||languageVoice[0]||voices[0]||null;
    utterance.rate=this.voiceStyle==='siri'?1.01:this.voiceSpeed;
    utterance.pitch=this.voiceStyle==='female'?1.08:this.voiceStyle==='male'?0.88:1;
    utterance.onend=()=>this.speaking=false;
    utterance.onerror=()=>{this.speaking=false;this.status='Unable to play voice output. Check your browser audio settings.';};
    // Some Chromium builds leave the synthesis engine paused after a previous request.
    synth.resume();
    window.setTimeout(()=>synth.speak(utterance),0);
  }
  stopSpeaking(){if('speechSynthesis' in window){window.speechSynthesis.cancel();this.speaking=false;}}
  confluenceStatus(){this.http.get<ConfluenceStatus>('/api/confluence/status').subscribe({next:v=>{this.confluenceConfigured=v.configured;this.confluenceConnected=v.connected;this.confluenceUrl=v.base_url;this.confluenceEmail=v.email;this.providerStatusCards[3]={key:'confluence',label:'Confluence',status:v};},error:()=>this.status='Unable to read Confluence connection status'});}
  jiraStatus(){this.http.get<JiraStatus>('/api/jira/status').subscribe({next:v=>{this.jiraConfigured=v.configured;this.jiraConnected=v.connected;this.jiraUrl=v.base_url;this.jiraEmail=v.email;this.providerStatusCards[2]={key:'jira',label:'Jira',status:v};this.loadJiraDailyComments();},error:()=>this.status='Unable to read Jira connection status'});}
  loadConnectionStatus(){this.connectionsLoading=true;this.http.get<ConnectionStatus>('/api/connections/status').subscribe({next:v=>{this.connectionStatus=v;this.setProviderStatusCards(v.providers);this.connectionsLoading=false;},error:()=>{this.connectionsLoading=false;this.status='Unable to read combined connection status. Showing individual provider statuses.';this.jiraStatus();this.confluenceStatus();}});}
  setProviderStatusCards(providers:ConnectionStatus['providers']){this.providerStatusCards=[{key:'microsoft',label:'Outlook',status:providers.microsoft},{key:'microsoft',label:'Teams',status:providers.microsoft},{key:'jira',label:'Jira',status:providers.jira},{key:'confluence',label:'Confluence',status:providers.confluence}];this.microsoftConfigured=providers.microsoft.configured;this.microsoftConnected=providers.microsoft.connected;this.microsoftEmail=providers.microsoft.account_email||'';this.jiraConfigured=providers.jira.configured;this.jiraConnected=providers.jira.connected;this.jiraUrl=providers.jira.base_url;this.jiraEmail=providers.jira.email;this.confluenceConfigured=providers.confluence.configured;this.confluenceConnected=providers.confluence.connected;this.confluenceUrl=providers.confluence.base_url;this.confluenceEmail=providers.confluence.email;}
  openConnections(){this.activeNav='connections';this.loadConnectionStatus();}
  connectJira(){this.jiraUrl=this.jiraUrl.trim().replace(/\/$/,'');this.jiraEmail=this.jiraEmail.trim();this.jiraToken=this.jiraToken.trim();if(!this.jiraUrl||!this.jiraEmail||!this.jiraToken){this.status='Enter the Jira site URL, email, and API token.';return;}this.status='Connecting to Jira…';this.http.post<JiraStatus>('/api/jira/connect',{base_url:this.jiraUrl,email:this.jiraEmail,api_token:this.jiraToken}).subscribe({next:v=>{this.jiraConfigured=v.configured;this.jiraConnected=v.connected;this.jiraToken='';this.providerStatusCards[2]={key:'jira',label:'Jira',status:v};this.status='Jira connected. Loading KAN-1…';this.startJiraSync();this.loadJiraIssue('KAN-1');},error:e=>this.status=e.error?.detail||'Unable to connect Jira'});}
  disconnectJira(){this.http.post('/api/jira/disconnect',{}).subscribe({next:()=>{this.jiraConnected=false;this.jiraConfigured=false;this.jiraIssues=[];this.status='Jira disconnected';},error:()=>this.status='Unable to disconnect Jira'});}
  searchJira(){const query=this.jiraQuery.trim();const board=this.jiraBoard.trim();if(!board&&!query){this.status='Select a board or enter a Jira search.';return;}if(!this.jiraConnected){this.status='Connect Jira before searching issues.';return;}this.jiraLoading=true;this.jiraSyncing=true;this.http.post<{issues:JiraIssue[]}>('/api/jira/search',{query,board_name:board}).subscribe({next:v=>{this.jiraIssues=v.issues;this.jiraLoading=false;this.jiraSyncing=false;this.jiraLastSynced=new Date().toISOString();this.jiraPage=1;this.status=`Synced ${v.issues.length} Jira issue${v.issues.length===1?'':'s'}`;},error:e=>{this.jiraLoading=false;this.jiraSyncing=false;this.status=e.error?.detail||'Unable to sync Jira';}});}
  startJiraSync(){if(this.jiraSyncTimer)clearInterval(this.jiraSyncTimer);this.jiraSyncTimer=setInterval(()=>{if(this.jiraSelectedIssue)this.loadJiraIssue(this.jiraSelectedIssue.key);else this.searchJira();},30000);}
  get jiraFilteredIssues(){const query=this.jiraQuery.trim().toLowerCase();const result=this.jiraIssues.filter(issue=>{const text=[issue.key,issue.summary,issue.description||'',issue.assignee].join(' ').toLowerCase();return(!query||text.includes(query))&&(this.jiraStatusFilter==='All'||issue.status===this.jiraStatusFilter)&&(this.jiraPriorityFilter==='All'||issue.priority===this.jiraPriorityFilter)&&(this.jiraAssigneeFilter==='All'||issue.assignee===this.jiraAssigneeFilter)&&(this.jiraSprintFilter==='All'||(issue.sprint||'No sprint')===this.jiraSprintFilter)&&(this.jiraEpicFilter==='All'||(issue.epic||'No epic')===this.jiraEpicFilter)&&(this.jiraTypeFilter==='All'||(issue.issue_type||'Task')===this.jiraTypeFilter);});return result.sort((a,b)=>{const av=String((a as any)[this.jiraSort]||'');const bv=String((b as any)[this.jiraSort]||'');return this.jiraSortDescending?bv.localeCompare(av):av.localeCompare(bv);});}
  get jiraPageIssues(){const start=(this.jiraPage-1)*this.jiraPageSize;return this.jiraFilteredIssues.slice(start,start+this.jiraPageSize);}
  get jiraPageCount(){return Math.max(1,Math.ceil(this.jiraFilteredIssues.length/this.jiraPageSize));}
  get jiraStatuses(){return [...new Set(this.jiraIssues.map(i=>i.status))];} get jiraPriorities(){return [...new Set(this.jiraIssues.map(i=>i.priority))];} get jiraAssignees(){return [...new Set(this.jiraIssues.map(i=>i.assignee))];} get jiraSprints(){return [...new Set(this.jiraIssues.map(i=>i.sprint||'No sprint'))];} get jiraEpics(){return [...new Set(this.jiraIssues.map(i=>i.epic||'No epic'))];} get jiraTypes(){return [...new Set(this.jiraIssues.map(i=>i.issue_type||'Task'))];}
  jiraKpi(status:string){return status==='Total'?this.jiraIssues.length:this.jiraIssues.filter(i=>i.status.toLowerCase().includes(status.toLowerCase())).length;}
  loadJiraIssue(issueKey:string){if(!this.jiraConnected)return;this.jiraLoading=true;this.jiraSyncing=true;this.http.get<JiraIssue>(`/api/jira/issues/${encodeURIComponent(issueKey)}`).subscribe({next:issue=>{this.jiraIssues=[issue,...this.jiraIssues.filter(item=>item.key!==issue.key)];this.jiraSelectedIssue=issue;this.jiraCommentIssue=issue;this.jiraLastSynced=new Date().toISOString();this.jiraLoading=false;this.jiraSyncing=false;this.loadJiraComments(issue);this.status=`Loaded ${issue.key} from Jira`;if(this.jiraStatusTimer)clearTimeout(this.jiraStatusTimer);this.jiraStatusTimer=setTimeout(()=>{if(this.status===`Loaded ${issue.key} from Jira`)this.status='';},4000);},error:e=>{this.jiraLoading=false;this.jiraSyncing=false;this.status=e.error?.detail||`Unable to load ${issueKey} from Jira`;}});}
  selectJiraIssue(issue:JiraIssue){this.jiraSelectedIssue=issue;this.jiraCommentIssue=issue;this.loadJiraComments(issue);}
  prepareJiraDailyComment(issue:JiraDailyIssue){this.jiraSelectedIssue=issue;this.jiraCommentIssue=issue;this.jiraReplyTo=undefined;this.jiraComment='';this.jiraVoiceState='idle';this.jiraVoiceTranscript='';this.jiraVoiceDraft='';this.jiraAiSuggestion='';this.jiraImproveOpen=false;this.jiraVoiceError='';this.jiraVoicePostedAt=undefined;this.loadJiraComments(issue);setTimeout(()=>document.getElementById(`jira-voice-${issue.key}`)?.focus());}
  startJiraVoice(issue:JiraIssue){this.jiraCommentIssue=issue;const Recognition=(window as any).SpeechRecognition||(window as any).webkitSpeechRecognition;if(!Recognition){this.jiraVoiceError='Voice input is not supported in this browser. You can still type your update.';this.status=this.jiraVoiceError;return;}this.jiraVoiceState='listening';this.jiraVoiceDuration=0;this.jiraVoiceFinalTranscript='';this.jiraVoiceTranscript='';this.jiraAiSuggestion='';this.jiraVoiceError='';this.jiraVoiceTimer=setInterval(()=>this.jiraVoiceDuration++,1000);const recognition=new Recognition();this.jiraVoiceRecognition=recognition;recognition.lang=this.inputLanguage||'en-US';recognition.continuous=true;recognition.interimResults=true;recognition.onresult=(event:any)=>{let interim='';for(let i=event.resultIndex;i<event.results.length;i++){const text=event.results[i][0].transcript;if(event.results[i].isFinal)this.jiraVoiceFinalTranscript+=text+' ';else interim+=text;}this.jiraVoiceTranscript=(this.jiraVoiceFinalTranscript+interim).trim();this.jiraComment=this.jiraVoiceTranscript;};recognition.onerror=()=>{this.stopJiraVoice();this.jiraVoiceError='We could not hear that update. Try again or type the update instead.';};recognition.onend=()=>{if(this.jiraVoiceState==='listening')this.stopJiraVoice();};recognition.start();}
  stopJiraVoice(){if(this.jiraVoiceTimer){clearInterval(this.jiraVoiceTimer);this.jiraVoiceTimer=undefined;}if(this.jiraVoiceRecognition){this.jiraVoiceRecognition.stop();this.jiraVoiceRecognition=undefined;}if(!this.jiraVoiceTranscript.trim()){this.jiraVoiceState='idle';return;}this.jiraVoiceState='processing';setTimeout(()=>{this.jiraAiSuggestion=this.correctJiraWriting(this.jiraVoiceTranscript);this.jiraVoiceDraft=this.jiraAiSuggestion;this.jiraComment=this.jiraVoiceTranscript;this.jiraVoiceState='ready';},450);}
  correctJiraWriting(text:string){let value=text.trim().replace(/\s+/g,' ');value=value.replace(/\bplese\b/gi,'Please').replace(/\bdeployed\b/gi,'deploy it').replace(/\bkan\s+(\d+)\s+bug\s+fixed\b/i,'KAN-$1 bug has been fixed').replace(/\bfixed bug\b/i,'I have fixed the reported issue');if(value&&!/[.!?]$/.test(value))value+='.';return value.charAt(0).toUpperCase()+value.slice(1);}
  improveJiraComment(style:string){const text=this.jiraComment.trim();if(!text)return;const base=this.correctJiraWriting(text).replace(/[.!?]$/,'');const suggestions:{[key:string]:string}={Professional:`${base} and verified the solution.`,Shorten:base,Expand:`${base} and documented the changes for the team to validate.`,Rephrase:`The reported issue has been resolved and is ready for validation.`,Formal:`Resolution has been completed for the reported issue and is ready for validation.`,Friendly:`${base} — the team can validate it when ready.`};this.jiraAiSuggestion=suggestions[style]||base;this.jiraImproveOpen=false;}
  useJiraSuggestion(){if(this.jiraAiSuggestion){this.jiraComment=this.jiraAiSuggestion;this.jiraVoiceDraft=this.jiraAiSuggestion;this.jiraVoiceState='ready';}}
  keepJiraOriginal(){this.jiraAiSuggestion='';this.jiraVoiceState='idle';}
  reRecordJiraVoice(issue:JiraDailyIssue){this.startJiraVoice(issue);}
  buildJiraVoiceUpdate(transcript:string){const sentences=transcript.split(/[.!?]+/).map(value=>value.trim()).filter(Boolean);const completed:string[]=[];const blockers:string[]=[];const risks:string[]=[];const nextSteps:string[]=[];sentences.forEach(sentence=>{const lower=sentence.toLowerCase();if(/block|blocker|waiting|approval|depend|stuck/.test(lower))blockers.push(sentence);else if(/risk|concern|might|could fail|uncertain/.test(lower))risks.push(sentence);else if(/tomorrow|next step|next|plan to|will start|going to/.test(lower))nextSteps.push(sentence);else completed.push(sentence);});if(!completed.length&&transcript.trim())completed.push(transcript.trim());if(!nextSteps.length)nextSteps.push('Continue progress and share the next milestone.');const section=(title:string,items:string[])=>`**${title}**\n${items.map(item=>`• ${item.charAt(0).toUpperCase()+item.slice(1)}${/[.!?]$/.test(item)?'':'.'}`).join('\n')}`;return [section('✅ Completed',completed),blockers.length?section('🚧 Blockers',blockers):'',risks.length?section('⚠ Risks',risks):'',section('➡ Next Steps',nextSteps)].filter(Boolean).join('\n\n');}
  jiraVoiceSeconds(){const minutes=Math.floor(this.jiraVoiceDuration/60).toString().padStart(2,'0');const seconds=(this.jiraVoiceDuration%60).toString().padStart(2,'0');return `${minutes}:${seconds}`;}
  toggleJiraSelection(issue:JiraIssue){issue.key&& (this.jiraSelectedKeys.has(issue.key)?this.jiraSelectedKeys.delete(issue.key):this.jiraSelectedKeys.add(issue.key));}
  toggleJiraSort(field:string){if(this.jiraSort===field)this.jiraSortDescending=!this.jiraSortDescending;else{this.jiraSort=field;this.jiraSortDescending=true;}}
  loadJiraComments(issue:JiraIssue){this.jiraCommentsLoading=true;this.jiraReplyTo=undefined;this.http.get<{comments:JiraComment[]}>(`/api/jira/issues/${encodeURIComponent(issue.key)}/comments`).subscribe({next:v=>{this.jiraComments=v.comments;this.jiraCommentsLoading=false;},error:e=>{this.jiraCommentsLoading=false;this.status=e.error?.detail||'Unable to load Jira comments';}});}
  prepareJiraReply(issue:JiraIssue,comment:JiraComment){this.jiraCommentIssue=issue;this.jiraReplyTo=comment;this.jiraComment='';}
  prepareJiraComment(issue:JiraIssue){this.jiraCommentIssue=issue;this.jiraComment=`Hi, this is ${this.currentUserName}. I reviewed ${issue.key} and will add an update shortly.`;this.status=`Draft comment ready for ${issue.key}. Review it, then choose “Yes, add comment”.`;
    if(this.voiceEnabled)this.speakAssistant(`${this.currentUserName}, I am not seeing your comment on ${issue.key}. I prepared a comment. Do you want me to add it?`);
  }
  addJiraComment(){if(this.jiraCommentSubmitting||!this.jiraCommentIssue||!this.jiraComment.trim())return;const issue=this.jiraCommentIssue;const voicePost=this.jiraVoiceState==='ready'&&this.jiraVoiceDraft.trim().length>0;this.jiraCommentSubmitting=true;this.http.post<{status:string}>('/api/jira/comment',{issue_key:issue.key,body:this.jiraComment.trim(),reply_to:this.jiraReplyTo?.id||null}).subscribe({next:()=>{if(!voicePost)this.jiraDailyIssues=this.jiraDailyIssues.filter(item=>item.key!==issue.key);this.status=`Comment added to ${issue.key}`;this.jiraCommentSubmitting=false;this.loadJiraComments(issue);if(voicePost){this.jiraVoiceState='posted';this.jiraVoicePostedAt=new Date();this.jiraVoicePostedPreview=this.jiraComment.trim();}else{this.jiraCommentIssue=undefined;this.jiraReplyTo=undefined;this.jiraComment='';}},error:e=>{this.jiraCommentSubmitting=false;this.status=e.error?.detail||'Unable to add Jira comment';}});}
  loadJiraDailyComments(){if(!this.jiraConnected)return;this.jiraDailyLoading=true;this.http.get<JiraIssue[]>('/api/jira/daily-comments').subscribe({next:issues=>{this.jiraDailyIssues=issues.map(issue=>({...issue,comment:''}));this.jiraDailyLoading=false;},error:()=>this.jiraDailyLoading=false});}
  connectConfluence(){
    this.confluenceUrl=this.confluenceUrl.trim().replace(/\/$/,'');
    this.confluenceEmail=this.confluenceEmail.trim();
    this.confluenceToken=this.confluenceToken.trim();
    if(!this.confluenceUrl||!this.confluenceEmail||!this.confluenceToken){this.status='Enter the Confluence site URL, email, and API token.';return;}
    this.http.post<ConfluenceStatus>('/api/confluence/connect',{base_url:this.confluenceUrl,email:this.confluenceEmail,api_token:this.confluenceToken}).subscribe({next:v=>{this.confluenceConfigured=v.configured;this.confluenceConnected=v.connected;this.confluenceToken='';this.providerStatusCards[3]={key:'confluence',label:'Confluence',status:v};this.status='Confluence connected. Paste a page link to search it.';},error:e=>this.status=e.error?.detail||'Unable to connect Confluence'});
  }
  disconnectConfluence(){this.http.post('/api/confluence/disconnect',{}).subscribe(()=>{this.confluenceConnected=false;this.confluenceConfigured=false;this.status='Confluence disconnected';});}
  private isConfluencePageReference(value:string){return /\/pages\/\d+|pageId=\d+|^\d+$/.test(value.trim());}
  loadConfluence(){
    const input=this.confluenceLink.trim();
    if(!input)return;
    if(this.isConfluencePageReference(input)){
      this.confluenceSourceLink=input;
      this.confluenceLink='Give me a summary';
      this.confluenceQuestion=this.confluenceLink;
      this.askConfluence(this.confluenceQuestion);
      return;
    }
    this.confluenceQuestion=input;
    this.askConfluence(input);
  }
  askConfluence(question=this.confluenceQuestion){
    if(!question.trim()){this.status='Enter a question for Confluence.';return;}
    this.confluenceQuestion=question;this.confluenceLoading=true;this.confluenceAnswer=undefined;
    const pageUrl=this.confluenceSourceLink.trim()||this.confluencePage?.url||'';
    this.http.post<ConfluenceAnswer>('/api/confluence/ask',{url:pageUrl,question,focus:this.confluenceFocus}).subscribe({next:v=>{this.confluenceAnswer=v;this.confluenceLoading=false;this.status='Answer generated from Confluence';if(this.voiceEnabled)this.speakAssistant(v.answer);},error:e=>{this.confluenceLoading=false;this.status=e.error?.detail||'Unable to answer from Confluence';}});
  }
  setVoiceStyle(style:string){this.voiceStyle=style;localStorage.setItem('voice-style',style);}
  setPreferredLanguage(language:string){this.preferredLanguage=language;localStorage.setItem('voice-language',language);}
  setVoiceSpeed(speed:number){this.voiceSpeed=Number(speed);localStorage.setItem('voice-speed',String(this.voiceSpeed));}
  speakWithStyle(text:string){this.speakAssistant(text);}
  listen(){const Recognition=(window as any).SpeechRecognition||(window as any).webkitSpeechRecognition;if(!Recognition){this.status='Speech recognition is not supported in this browser';return;}const r=new Recognition();r.lang=this.inputLanguage;this.listening=true;r.onresult=(e:any)=>{const text=e.results[0][0].transcript;const yes=/^(yes|yeah|yep|send it|add it|do it)\b/i.test(text.trim());if(yes&&this.draft)this.send();else if(yes&&this.jiraCommentIssue)this.addJiraComment();else if(this.confluencePage||this.confluenceLink){this.confluenceQuestion=text;this.askConfluence(text);}else this.instruction=text;this.listening=false;};r.onerror=()=>this.listening=false;r.onend=()=>this.listening=false;r.start();}
}