import { useEffect, useId, useRef } from 'react'
import './unsaved-changes.css'

export function DiscardDialog({ open, label, dirty, pending, stay, discard }: {
  open: boolean; label: string; dirty: boolean; pending: boolean; stay: () => void; discard: () => void
}) {
  const ref = useRef<HTMLDialogElement>(null), stayButton = useRef<HTMLButtonElement>(null)
  const id = useId()
  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) { dialog.showModal(); stayButton.current?.focus() }
    else if (!open && dialog.open) dialog.close()
  }, [open])
  return <dialog ref={ref} className="editing-confirmation" aria-labelledby={id + '-title'} aria-describedby={id + '-description'}
    onCancel={event => { event.preventDefault(); stay() }}>
    <h2 id={id + '-title'}>{dirty ? 'Abandonner les modifications ?' : pending ? 'Quitter pendant une opération ?' : 'Continuer la navigation ?'}</h2>
    <div id={id + '-description'}><p>{dirty ? label + " : vos modifications ne sont pas enregistrées. Rester les conserve dans cet éditeur ; abandonner permet de quitter ou de réinitialiser la saisie." : pending ? label + " : restez pour attendre le résultat de l’opération en cours." : "L’opération est terminée. Vous pouvez rester pour consulter son résultat ou continuer."}</p>
      {pending && <p>Une opération est en cours et peut encore se terminer côté serveur. Quitter ne l’annule pas. Vérifiez son résultat avant de la répéter.</p>}
    </div>
    <div className="editing-confirmation-actions"><button ref={stayButton} type="button" className="editing-stay" onClick={stay}>Rester</button><button type="button" onClick={discard}>{dirty ? 'Abandonner et continuer' : pending ? 'Quitter et continuer' : 'Continuer'}</button></div>
  </dialog>
}

export function VerifySavedState({ href }: { href: string }) {
  return <p><a href={href} target="_blank" rel="noopener noreferrer">Vérifier l’état enregistré dans un autre onglet</a> · La saisie de cet éditeur reste en place. Cette vérification n’enregistre et ne renvoie rien automatiquement.</p>
}

