import {Component,inject,computed} from '@angular/core';
import {Workspace} from '../../services/workspace';
@Component({selector:'app-activity-chart',imports:[],templateUrl:'./activity-chart.html',styleUrl:'./activity-chart.css'})
export class ActivityChart {
 private store=inject(Workspace);
 readonly points=computed(()=>{const drafts=this.store.state().drafts;const dates=Array.from({length:7},(_,i)=>{const d=new Date();d.setUTCDate(d.getUTCDate()-6+i);return d.toISOString().slice(0,10);});const counts=dates.map(date=>drafts.filter(d=>d.status==='Sent'&&d.sentDate===date).length);const max=Math.max(1,...counts);return dates.map((date,i)=>({date,label:new Date(date+'T12:00:00Z').toLocaleDateString('en',{weekday:'short'}),count:counts[i],height:counts[i]/max*100}));});
}
