import { CalendarDays, Clock, MapPin, Users, AlarmClock, Building2, Mail, Phone } from "lucide-react";
import { countdownLabel } from "../api.js";

function Fact({ icon: Icon, label, value, sub, tone }) {
  if (!value) return null;
  return (
    <div className={"fact" + (tone ? " fact-" + tone : "")}>
      <div className="fact-icon">
        <Icon size={17} />
      </div>
      <div className="fact-body">
        <span className="fact-label">{label}</span>
        <span className="fact-value">{value}</span>
        {sub && <span className={"pill pill-" + sub.tone}>{sub.text}</span>}
      </div>
    </div>
  );
}

export default function Facts({ facts }) {
  if (!facts) return null;
  const elig = (facts.cats?.eligibility || []).find((s) => /eligible|open to|intended|only for/i.test(s)) || (facts.cats?.eligibility || [])[0];
  const eligText = elig ? elig.replace(/^(eligible students|eligibility|eligible|open to)\s*[:\-]\s*/i, "") : null;
  return (
    <div className="facts">
      <Fact icon={CalendarDays} label="Event date" value={facts.event_date?.text} sub={countdownLabel(facts.event_date?.iso)} />
      <Fact icon={Clock} label="Time" value={facts.time} />
      <Fact icon={MapPin} label="Venue" value={facts.venue} />
      <Fact icon={AlarmClock} label={facts.deadline?.label ? `${cap(facts.deadline.label)} deadline` : "Deadline"} value={facts.deadline?.text} sub={countdownLabel(facts.deadline?.iso)} tone="warn" />
      <Fact icon={Users} label="Eligibility" value={eligText && eligText.length > 90 ? eligText.slice(0, 88) + "…" : eligText} />
      <Fact icon={Building2} label="Department" value={facts.department} />
      <Fact icon={Mail} label="Email" value={facts.emails?.[0]} />
      <Fact icon={Phone} label="Phone" value={facts.phones?.[0]} />
    </div>
  );
}

const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
