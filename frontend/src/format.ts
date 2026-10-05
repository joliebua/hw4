const CATEGORY_LABELS: Record<string, string> = {
  't-shirt': 'T-Shirts',
  'long-sleeve': 'Long Sleeves',
  crewneck: 'Crewnecks',
  hoodie: 'Hoodies',
  'quarter-zip': 'Quarter-Zips',
  jacket: 'Jackets & Full-Zips',
  other: 'Other',
}

export const categoryLabel = (c: string) => CATEGORY_LABELS[c] ?? c

export const capitalize = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)

export const price = (n: number) =>
  n.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: Number.isInteger(n) ? 0 : 2,
  })

export const SIZES = ['XS', 'S', 'M', 'L', 'XL', 'XXL']
