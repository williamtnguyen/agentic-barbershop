import { AlertCircle, CheckCircle2, Clock } from "lucide-react";
import { type FormEvent, type ReactNode, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Calendar, type DateString, monthKey } from "@/components/ui/calendar";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  ApiError,
  type BookingResult,
  createBooking,
  getOpenDays,
  getOpenTimes,
  getServices,
  type Service,
  type TimeSlot,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const dayLabel = new Intl.DateTimeFormat(undefined, { weekday: "long", month: "short", day: "numeric" });

function formatDay(value: DateString) {
  const [y, m, d] = value.split("-").map(Number);
  return dayLabel.format(new Date(y, m - 1, d));
}

function validPhone(phone: string) {
  const digits = phone.replace(/\D/g, "");
  return digits.length === 10 || (digits.length === 11 && digits.startsWith("1"));
}

function messageOf(error: unknown) {
  return error instanceof ApiError ? error.message : "Something went wrong. Try again.";
}

function Section({ title, children, id }: { title: string; children: ReactNode; id?: string }) {
  return (
    <section aria-labelledby={id} className="space-y-3">
      <h2 id={id} className="text-sm font-semibold">
        {title}
      </h2>
      {children}
    </section>
  );
}

function Notice({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div
      role="alert"
      className="flex items-center gap-3 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2.5 text-sm text-destructive"
    >
      <AlertCircle className="size-4 shrink-0" aria-hidden />
      <span className="flex-1">{children}</span>
      {action}
    </div>
  );
}

const EMPTY_FORM = { firstName: "", lastName: "", phone: "", note: "" };

export function BookPanel() {
  const thisMonth = useRef(new Date(new Date().getFullYear(), new Date().getMonth(), 1)).current;

  const [services, setServices] = useState<Service[] | null>(null);
  const [servicesError, setServicesError] = useState<string | null>(null);
  const [service, setService] = useState<Service | null>(null);
  const [month, setMonth] = useState(thisMonth);
  const [openDays, setOpenDays] = useState<Set<string> | null>(null);
  const [day, setDay] = useState<DateString | null>(null);
  const [times, setTimes] = useState<TimeSlot[] | null>(null);
  const [time, setTime] = useState<TimeSlot | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [phoneTouched, setPhoneTouched] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [booked, setBooked] = useState<BookingResult | null>(null);
  const [reloadTimes, setReloadTimes] = useState(0);

  const timesRef = useRef<HTMLDivElement>(null);
  const detailsRef = useRef<HTMLDivElement>(null);

  const loadServices = () => {
    setServicesError(null);
    getServices()
      .then(setServices)
      .catch((err) => setServicesError(messageOf(err)));
  };
  useEffect(loadServices, []);

  useEffect(() => {
    if (!service) return;
    let current = true;
    setOpenDays(null);
    setError(null);
    getOpenDays(service.id, monthKey(month))
      .then((days) => current && setOpenDays(new Set(days)))
      .catch((err) => {
        if (!current) return;
        setOpenDays(new Set());
        setError(messageOf(err));
      });
    return () => {
      current = false;
    };
  }, [service, month]);

  useEffect(() => {
    if (!service || !day) return;
    let current = true;
    setTimes(null);
    getOpenTimes(service.id, day)
      .then((slots) => current && setTimes(slots))
      .catch((err) => {
        if (!current) return;
        setTimes([]);
        setError(messageOf(err));
      });
    return () => {
      current = false;
    };
  }, [service, day, reloadTimes]);

  useEffect(() => {
    if (day) timesRef.current?.scrollIntoView?.({ behavior: "smooth", block: "nearest" });
  }, [day]);
  useEffect(() => {
    if (time) detailsRef.current?.scrollIntoView?.({ behavior: "smooth", block: "nearest" });
  }, [time]);

  function chooseService(next: Service) {
    if (next.id === service?.id) return;
    setService(next);
    setMonth(thisMonth);
    setDay(null);
    setTime(null);
    setTimes(null);
  }

  function chooseDay(next: DateString) {
    setDay(next);
    setTime(null);
    setError(null);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setPhoneTouched(true);
    if (!service || !time || !form.firstName.trim() || !validPhone(form.phone)) return;
    setSubmitting(true);
    setError(null);
    try {
      setBooked(
        await createBooking({
          serviceId: service.id,
          start: time.start,
          phone: form.phone,
          firstName: form.firstName.trim(),
          lastName: form.lastName.trim(),
          note: form.note.trim(),
        }),
      );
    } catch (err) {
      setError(messageOf(err));
      if (err instanceof ApiError && err.status === 409) {
        setTime(null);
        setReloadTimes((n) => n + 1);
      }
    } finally {
      setSubmitting(false);
    }
  }

  function startOver() {
    setBooked(null);
    setService(null);
    setDay(null);
    setTime(null);
    setTimes(null);
    setForm(EMPTY_FORM);
    setPhoneTouched(false);
    setError(null);
  }

  if (booked) {
    return (
      <div className="flex flex-col items-center px-6 py-12 text-center">
        <CheckCircle2 className="size-12 text-success" aria-hidden />
        <h2 className="mt-4 text-lg font-semibold">You're booked, {booked.client}</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {booked.service} on {booked.when}
        </p>
        <Button variant="outline" className="mt-6" onClick={startOver}>
          Book another appointment
        </Button>
      </div>
    );
  }

  const phoneInvalid = phoneTouched && !validPhone(form.phone);

  return (
    <div className="space-y-7 px-4 py-5">
      <Section title="Service" id="service-heading">
        {servicesError && (
          <Notice
            action={
              <Button variant="outline" size="sm" onClick={loadServices}>
                Try again
              </Button>
            }
          >
            {servicesError}
          </Notice>
        )}
        {!services && !servicesError && (
          <div className="space-y-2" aria-label="Loading services">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-16 animate-pulse rounded-lg bg-muted" />
            ))}
          </div>
        )}
        {services && (
          <div className="grid gap-2" role="radiogroup" aria-labelledby="service-heading">
            {services.map((s) => {
              const selected = s.id === service?.id;
              return (
                <button
                  key={s.id}
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  onClick={() => chooseService(s)}
                  className={cn(
                    "rounded-lg border px-4 py-3 text-left transition-colors outline-none hover:bg-accent focus-visible:ring-[3px] focus-visible:ring-ring/50",
                    selected && "border-primary bg-primary/5 hover:bg-primary/5",
                  )}
                >
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="font-medium">{s.name}</span>
                    <span className="text-sm font-medium">{s.price}</span>
                  </div>
                  <div className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
                    <Clock className="size-3.5" aria-hidden />
                    {s.minutes} min
                  </div>
                  {s.description && (
                    <p className="mt-1.5 text-sm text-muted-foreground">{s.description}</p>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </Section>

      {service && (
        <Section title="Day">
          <Calendar
            month={month}
            onMonthChange={(m) => {
              setMonth(m);
              setDay(null);
              setTime(null);
            }}
            minMonth={thisMonth}
            selected={day ?? undefined}
            onSelect={chooseDay}
            isAvailable={(d) => openDays?.has(d) ?? false}
            loading={openDays === null}
          />
          {openDays && openDays.size === 0 && !error && (
            <p className="text-sm text-muted-foreground">
              No openings this month. Try the next month.
            </p>
          )}
        </Section>
      )}

      {service && day && (
        <div ref={timesRef}>
          <Section title={`Time on ${formatDay(day)}`}>
            {times === null ? (
              <div className="grid grid-cols-3 gap-2" aria-label="Loading times">
                {Array.from({ length: 6 }, (_, i) => (
                  <div key={i} className="h-9 animate-pulse rounded-md bg-muted" />
                ))}
              </div>
            ) : times.length === 0 ? (
              <p className="text-sm text-muted-foreground">No open times left. Pick another day.</p>
            ) : (
              <div className="grid grid-cols-3 gap-2" role="radiogroup" aria-label="Times">
                {times.map((t) => (
                  <Button
                    key={t.start}
                    role="radio"
                    aria-checked={t.start === time?.start}
                    variant={t.start === time?.start ? "default" : "outline"}
                    onClick={() => {
                      setTime(t);
                      setError(null);
                    }}
                  >
                    {t.label}
                  </Button>
                ))}
              </div>
            )}
          </Section>
        </div>
      )}

      {error && <Notice>{error}</Notice>}

      {service && day && time && (
        <div ref={detailsRef}>
          <Section title="Your details">
            <form onSubmit={submit} className="space-y-4" noValidate>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label htmlFor="first-name">First name</Label>
                  <Input
                    id="first-name"
                    autoComplete="given-name"
                    required
                    value={form.firstName}
                    onChange={(e) => setForm({ ...form, firstName: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="last-name">
                    Last name <span className="font-normal text-muted-foreground">(optional)</span>
                  </Label>
                  <Input
                    id="last-name"
                    autoComplete="family-name"
                    value={form.lastName}
                    onChange={(e) => setForm({ ...form, lastName: e.target.value })}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="phone">Mobile number</Label>
                <Input
                  id="phone"
                  type="tel"
                  autoComplete="tel"
                  inputMode="tel"
                  required
                  aria-invalid={phoneInvalid}
                  aria-describedby={phoneInvalid ? "phone-error" : undefined}
                  value={form.phone}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  onBlur={() => form.phone && setPhoneTouched(true)}
                />
                {phoneInvalid && (
                  <p id="phone-error" className="text-xs text-destructive">
                    Enter a 10-digit US number.
                  </p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="note">
                  Note for the barber{" "}
                  <span className="font-normal text-muted-foreground">(optional)</span>
                </Label>
                <Textarea
                  id="note"
                  rows={2}
                  maxLength={500}
                  placeholder="Low fade, keep length on top"
                  value={form.note}
                  onChange={(e) => setForm({ ...form, note: e.target.value })}
                  className="min-h-0"
                />
              </div>
              <Button
                type="submit"
                className="w-full"
                size="lg"
                disabled={submitting || !form.firstName.trim() || !form.phone.trim()}
              >
                {submitting ? "Booking…" : `Book ${formatDay(day)} at ${time.label}`}
              </Button>
              <p className="text-center text-xs text-muted-foreground">
                {service.name}, {service.minutes} min, {service.price}
              </p>
            </form>
          </Section>
        </div>
      )}
    </div>
  );
}
