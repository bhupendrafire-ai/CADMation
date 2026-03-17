function normalizeText(value) {
  return `${value || ''}`.trim().replace(/\s+/g, ' ')
}

function titleize(value) {
  return normalizeText(value)
    .split(' ')
    .filter(Boolean)
    .map((token) => token.charAt(0).toUpperCase() + token.slice(1).toLowerCase())
    .join(' ')
}

const keywordMap = [
  { match: /wear[_ ]?plate/i, suggestion: 'Wear Plate' },
  { match: /setting[_ ]?plate/i, suggestion: 'Setting Plate' },
  { match: /transporta?ion[_ ]?strap/i, suggestion: 'Transportation Strap' },
  { match: /gas[_ ]?spring.*mtg[_ ]?plate|mtg[_ ]?plate.*gas[_ ]?spring/i, suggestion: 'Gas Spring Mtg Plate' },
  { match: /gas[_ ]?spring/i, suggestion: 'Gas Spring' },
  { match: /stacker[_ ]?block/i, suggestion: 'Stacker Block' },
  { match: /stacker[_ ]?pin/i, suggestion: 'Stacker Pin' },
  { match: /stopper[_ ]?plate/i, suggestion: 'Stopper Plate' },
  { match: /part[_ ]?gauge[_ ]?pin/i, suggestion: 'Part Gauge Pin' },
  { match: /hitting[_ ]?block|hiiting[_ ]?block/i, suggestion: 'Hitting Block' },
  { match: /lower[_ ]?flange[_ ]?steel/i, suggestion: 'Lower Flange Steel' },
  { match: /upper[_ ]?flange[_ ]?steel/i, suggestion: 'Upper Flange Steel' },
  { match: /lower[_ ]?pad[_ ]?steel/i, suggestion: 'Lower Pad Steel' },
  { match: /adapter[_ ]?lower[_ ]?and[_ ]?upper[_ ]?die/i, suggestion: 'Adapter Lower And Upper Die' },
  { match: /balancer/i, suggestion: 'Balancer Block' },
]

export function getNameSuggestions(row) {
  const source = `${row?.description || ''} ${row?.partNumber || ''} ${row?.instanceName || ''} ${row?.name || ''}`
  const suggestions = new Set()
  keywordMap.forEach(({ match, suggestion }) => {
    if (match.test(source)) suggestions.add(suggestion)
  })

  const partNumber = normalizeText(row?.partNumber)
  if (partNumber) {
    const cleaned = partNumber
      .replace(/^\d+[-_ ]*/, '')
      .replace(/[.]+/g, ' ')
      .replace(/[_-]+/g, ' ')
    if (cleaned && !/\b(catpart|catproduct)\b/i.test(cleaned)) {
      suggestions.add(titleize(cleaned))
    }
  }

  const instanceName = normalizeText(row?.instanceName || row?.name)
  if (instanceName) {
    const cleaned = instanceName
      .replace(/^\d+[-_ ]*/, '')
      .replace(/[.]+/g, ' ')
      .replace(/[_-]+/g, ' ')
    if (cleaned) suggestions.add(titleize(cleaned))
  }

  const currentDescription = normalizeText(row?.description)
  if (currentDescription) suggestions.add(currentDescription)

  return Array.from(suggestions).filter(Boolean).slice(0, 8)
}
