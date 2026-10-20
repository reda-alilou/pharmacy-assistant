import { MapPin, Phone } from 'lucide-react'
import type { PatientResponse } from '@/shared/api/schema'
import { collected, phoneLink } from '../lib/presentation'
import { SourceLink } from './source-link'

export function PharmacyResults({ response }: { response: PatientResponse }) {
  return <>{response.pharmacy && response.pharmacy.pharmacies.length > 0 && <section className="pharmacy-results" aria-label="Pharmacies trouvées"><p className="directory-notice">Annuaire partiel de Rabat · Classement par nom, sans calcul de distance</p>{response.pharmacy.city_defaulted && <p className="muted text-sm">La recherche a été limitée à Rabat, la ville couverte par cet annuaire.</p>}
      {response.pharmacy.pharmacies.map(pharmacy => <article className="pharmacy-card" key={pharmacy.pharmacy_id}><h3>{pharmacy.name}</h3><p className="pharmacy-address"><MapPin size={16} aria-hidden="true" /><span>{pharmacy.address ?? 'Adresse non renseignée'} · {pharmacy.city}</span></p><div className="pharmacy-contact">{phoneLink(pharmacy.phone) ? <a href={phoneLink(pharmacy.phone)} className="phone-link"><Phone size={15} aria-hidden="true" />{pharmacy.phone}</a> : <span className="muted text-sm">{pharmacy.phone ?? 'Téléphone non renseigné'}</span>}<SourceLink url={pharmacy.source_url}>{pharmacy.source}</SourceLink></div><p className="collection-date">{collected(pharmacy.fetched_at_utc)}</p></article>)}
      {response.pharmacy.results_truncated && <p className="muted text-sm">{response.pharmacy.pharmacies.length} résultats affichés sur {response.pharmacy.result_count}. Précisez le nom ou le quartier pour affiner.</p>}<p className="directory-notice">Horaires inconnus · Garde non vérifiée · Stock non vérifié</p>
    </section>}</>
}
