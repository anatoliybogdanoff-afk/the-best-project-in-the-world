export function duckSvg({spy=false, look=false, width=110, className=''}={}) {
 return `<svg class="duck ${className} ${spy?'spy':''}" width="${width}" height="${width*114/118}" viewBox="0 0 118 114" fill="none" aria-hidden="true">
 <ellipse cx="54" cy="106" rx="36" ry="5" fill="#473346" opacity=".08"/>
 <g class="duck-foot foot-left"><path d="M36 94v10l-12 3h20" stroke="#DF914A" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/></g>
 <g class="duck-foot foot-right"><path d="M64 94v10l-10 4h20" stroke="#DF914A" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/></g>
 <path d="M24 61 8 52c-2 24 9 44 36 44 26 0 42-12 41-32-1-17-19-26-35-20-12 4-17 12-26 17Z" fill="${spy?'#514353':'#F3C65C'}"/>
 <path d="M25 70c2 15 14 19 24 15 9-4 12-11 9-17" fill="${spy?'#746173':'#E9B84C'}"/>
 ${spy?'<path d="m59 53-7 16 8 14 12-18-5-12" fill="#D5B68E"/><path d="m61 56 5 8-5 13-5-10" fill="#F0D2AB"/><circle cx="72" cy="77" r="2" fill="#D5B68E"/>':''}
 <g class="duck-head ${look?'looks-back':''}">
 <path d="M50 50c-8-9-8-24 0-33C60 5 79 8 88 20c9 14 2 31-13 36" fill="#F5D06A"/>
 <path d="m85 31 22 6c5 2 5 7-1 9l-22 1" fill="#E99A51"/>
 <path d="m89 39 15 1" stroke="#C77C3E" stroke-width="1.5" stroke-linecap="round"/>
 ${spy?'<g class="duck-shades"><path d="M60 28h16v10c-8 5-15 1-16-4v-6Zm19 0h15v7c-4 7-13 7-15 1v-8Z" fill="#302B35"/><path d="M75 30h5m-22-1-9-3" stroke="#302B35" stroke-width="3"/><path d="m64 30 5 5m15-5 4 4" stroke="#FFF" opacity=".25" stroke-width="2"/></g>':'<ellipse class="duck-eye" cx="77" cy="27" rx="3" ry="4" fill="#3D3238"/><circle cx="78" cy="26" r=".9" fill="#FFF"/><path d="m73 19 7-1" stroke="#BD9446" stroke-width="2" stroke-linecap="round"/>'}
 <path d="m58 10 2-7 5 6" stroke="#E2B957" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
 </g></svg>`;
}

export const duckMotionCss = `
.duck{overflow:visible;vertical-align:middle}.duck-foot{transform-box:fill-box;transform-origin:center top;animation:waddle .55s ease-in-out infinite alternate}.foot-right{animation-delay:-.55s}.duck-eye{animation:blink 5s infinite}.duck-head.looks-back{transform-box:fill-box;transform-origin:center;animation:lookback 5s ease-in-out infinite}.spy .duck-foot{animation-duration:.3s}.spy .duck-shades{animation:shades 4s ease-in-out infinite;transform-box:fill-box;transform-origin:center}
@keyframes waddle{from{transform:rotate(-12deg)}to{transform:rotate(13deg)}}@keyframes blink{0%,44%,48%,100%{transform:scaleY(1)}46%{transform:scaleY(.1)}}@keyframes lookback{0%,25%,65%,100%{transform:scaleX(1)}35%,52%{transform:scaleX(-1)}}@keyframes shades{0%,70%,100%{transform:translateY(0)}76%,84%{transform:translateY(-2px)}}
@media(prefers-reduced-motion:reduce){.duck *{animation:none!important}}
`;
