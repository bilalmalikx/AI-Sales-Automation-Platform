export function today(timezone = 'Asia/Karachi'): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date());
}
export function dateLabel(value: string): string {
  return new Date(value + 'T12:00:00').toLocaleDateString('en', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}
export function minutes(value: string): number {
  const [h, m] = value.split(':').map(Number);
  return h * 60 + m;
}
export function meetingsOverlap(
  a: {
    date: string;
    time: string;
    duration: string;
  },
  b: {
    date: string;
    time: string;
    duration: string;
  },
): boolean {
  return (
    a.date === b.date &&
    minutes(a.time) < minutes(b.time) + Number(b.duration) &&
    minutes(b.time) < minutes(a.time) + Number(a.duration)
  );
}

export function zonedTimestamp(date:string,time:string,timezone:string):string {
 const wall=Date.parse(`${date}T${time}:00Z`);let guess=wall;
 for(let i=0;i<3;i++){
  const parts=Object.fromEntries(new Intl.DateTimeFormat('en-CA',{timeZone:timezone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).formatToParts(new Date(guess)).map(p=>[p.type,p.value]));
  const local=Date.parse(`${parts['year']}-${parts['month']}-${parts['day']}T${parts['hour']}:${parts['minute']}:${parts['second']}Z`);
  guess+=wall-local;
 }
 return new Date(guess).toISOString();
}
