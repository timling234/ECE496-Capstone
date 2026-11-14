"""Shared feed styles and instant-save appearance picker."""
THEMES={
    'classic':('Classic','Familiar social cards'),
    'precision':('Precision','Compact research briefing'),
    'slate':('Slate','A focused, dark workspace.'),
}


def selector(selected='classic'):
    cards=[]
    for key,(name,description) in THEMES.items():
        mini=''.join('<span class="theme-mini-card"><i class="theme-mini-heading"></i>'+('<i class="theme-mini-image"></i>' if i!=1 else '')+'<i class="theme-mini-line"></i><i class="theme-mini-line short"></i><i class="theme-mini-link"></i></span>' for i in range(3))
        cards.append('<label class="theme-option"><input type="radio" name="style" value="'+key+'" '+('checked ' if selected==key else '')+'><span class="theme-thumbnail mini-'+key+'" aria-hidden="true">'+mini+'<span class="theme-check">✓</span></span><span class="theme-title">'+name+'</span><span class="theme-description">'+description+'</span></label>')
    return PICKER_STYLE+PRECISION_PICKER+'<fieldset class="theme-picker"><legend>Feed style</legend><div class="theme-options">'+''.join(cards)+'</div></fieldset><p class="theme-hint">Changes save automatically and apply to your embedded feed and Mock Website.</p>'


PICKER_STYLE='''<style>
.theme-picker{border:0;padding:0;margin:0 0 12px;max-width:860px}.theme-picker legend{font-size:13px;font-weight:600;margin-bottom:12px}.theme-options{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;background:#f5f5f7;padding:16px;border:1px solid #e7e8ec;border-radius:18px}.theme-option{position:relative;cursor:pointer;min-width:0}.theme-option>input{position:absolute;opacity:0;width:1px;height:1px}.theme-thumbnail{position:relative;display:flex;align-items:flex-start;gap:7px;height:132px;box-sizing:border-box;padding:14px 10px;background:white;border:2px solid transparent;border-radius:12px;box-shadow:0 2px 8px #17253612;overflow:hidden;transition:border-color .15s,box-shadow .15s}.theme-option:has(input:checked) .theme-thumbnail{border-color:#007aff;box-shadow:0 0 0 3px #007aff18}.theme-option:has(input:focus-visible) .theme-thumbnail{outline:3px solid #007aff;outline-offset:3px}.theme-option:has(input:disabled){cursor:wait;opacity:.7}.theme-title{display:block;text-align:center;font-size:13px;font-weight:600;margin-top:10px;color:#1d2530}.theme-description{display:block;text-align:center;font-size:11px;color:#6b7280;margin-top:4px}.theme-check{position:absolute;right:6px;bottom:6px;display:none;width:20px;height:20px;text-align:center;line-height:20px;border-radius:50%;background:#007aff;color:white;font-size:13px;font-weight:700}.theme-option:has(input:checked) .theme-check{display:block}.theme-mini-card{flex:1;min-width:0;padding:7px 5px;background:#f7f7f7;border-radius:4px}.theme-mini-card i{display:block}.theme-mini-heading{height:4px;width:80%;background:#7c8794;margin-bottom:7px;border-radius:2px}.theme-mini-image{height:37px;background:linear-gradient(135deg,#d5e2ec,#96aec4);margin-bottom:7px;border-radius:2px}.theme-mini-line{height:3px;background:#bac2cb;margin-bottom:4px}.theme-mini-line.short{width:65%}.theme-mini-link{height:3px;background:#4596f0;width:42%;margin-top:7px}.mini-precision .theme-mini-card{background:white;border:1px solid #dbe2eb;border-top:2px solid #2963a3;border-radius:1px}.mini-precision .theme-mini-image{height:31px;border-radius:0;background:linear-gradient(140deg,#dce5ee,#adc2d9)}.mini-slate{background:#101c2b}.mini-slate .theme-mini-card{background:#1c2b3d;border:1px solid #314358}.mini-slate .theme-mini-heading{background:#c6d3e2}.mini-slate .theme-mini-line{background:#60758c}.mini-slate .theme-mini-image{background:linear-gradient(140deg,#334d65,#658ba7)}.mini-slate .theme-mini-link{background:#80beff}.theme-hint{font-size:12px;color:#667588;margin:0 0 18px}@media(max-width:600px){.theme-options{gap:8px;padding:10px}.theme-thumbnail{height:100px;padding:10px 5px;gap:4px}.theme-mini-card{padding:4px 3px}.theme-mini-image{height:24px}.theme-description{display:none}}
</style>'''


def theme_css(style,accent,color_theme='auto'):
    # Only allow colors already accepted by the settings validation.
    import re
    if not re.fullmatch(r'#[0-9a-fA-F]{6}',accent):accent='#215e95'
    colors=palette(style,accent,color_theme)
    if style=='classic':return '<style>'+colors+'</style>'
    common='''.news-theme-STYLE{--theme-link:LINK}.news-theme-STYLE .news-body-link,.news-theme-STYLE .news-tag,.news-theme-STYLE [data-read-more]{color:var(--theme-link)}'''.replace('STYLE',style).replace('LINK',accent if style=='precision' else '#8bc5ff')
    if style=='precision':
        css='''.news-theme-precision{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.news-theme-precision .news-page{gap:20px}.news-theme-precision .news-card{background:white;border:1px solid #d8e2ed!important;border-top:3px solid var(--theme-link)!important;border-radius:4px!important;padding:18px!important;box-shadow:0 3px 12px #152e4b08}.news-theme-precision .news-publisher{padding-bottom:13px;border-bottom:1px solid #e5ebf1}.news-theme-precision .news-name{color:#172c46;font-weight:650}.news-theme-precision .news-date{font:11px ui-monospace,SFMono-Regular,Consolas,monospace;color:#65788d;margin-top:5px}.news-theme-precision .news-post{background:#fafcfe;border:0;border-radius:0}.news-theme-precision .news-inner{padding:14px 0}.news-theme-precision .content{color:#283c52;line-height:1.5}.news-theme-precision .content.collapsed{max-height:4.5em}.news-theme-precision .news-actions{border-top:1px solid #e5ebf1;padding-top:14px;color:#5b6f85}.news-theme-precision .news-media{background:#eaf0f6}.news-theme-precision .news-dots button[aria-current=page]{background:var(--theme-link)}.news-theme-precision .news-arrow{background:#274766e8}.news-theme-precision .news-stream-list .news-card{border-top:0!important;border-bottom:8px solid #eaf0f6!important;border-radius:0!important}'''
    else:
        css='''.news-theme-slate{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#101c2b;color:#e6edf7;border-radius:14px;padding:20px 20px 24px;color-scheme:dark}.news-theme-slate .news-card{background:#1a293b;border:1px solid #314359!important;border-radius:10px!important;padding:16px!important}.news-theme-slate .news-name{color:#edf3fc}.news-theme-slate .news-date{color:#a4b5c9}.news-theme-slate .news-post{background:#142233;border:1px solid #314359}.news-theme-slate .news-media{background:#142233}.news-theme-slate .news-avatar{background:#314359;color:#adbed1}.news-theme-slate .content{color:#dee7f2;line-height:1.45}.news-theme-slate .content.collapsed{max-height:4.35em}.news-theme-slate .news-actions{color:#b3c3d6}.news-theme-slate .news-arrow{background:#3c5874ed}.news-theme-slate .news-prev{left:4px}.news-theme-slate .news-next{right:4px}.news-theme-slate .news-dots button{background:#5b718c}.news-theme-slate .news-dots button[aria-current=page]{background:#9dccff}.news-theme-slate button:focus-visible,.news-theme-slate a:focus-visible{outline-color:#9dccff}.news-theme-slate.news-post-stream{padding:0}.news-theme-slate .news-stream-list .news-card{border-bottom:8px solid #101c2b!important;border-radius:0!important}.news-theme-slate.news-stream-mode{padding:0}'''
    return '<style>'+common+css+(PRECISION_LAYOUT if style=='precision' else '')+colors+'</style>'


def color_selector(selected='auto'):
    options=''.join('<label><input type="radio" name="color_theme" value="'+key+'" '+('checked' if key==selected else '')+'><span>'+name+'</span></label>' for key,name in [('auto','Style default'),('light','Light'),('dark','Dark')])
    return '<fieldset class="feed-colors"><legend>Color theme</legend><div class="color-segments">'+options+'</div></fieldset>'


PRECISION_PICKER='''<style>
.mini-precision{flex-direction:column;gap:6px}.mini-precision .theme-mini-card{position:relative;flex:none;display:block;width:100%;height:28px;box-sizing:border-box;padding:5px 8px 3px 45px;border:1px solid #dbe2eb;border-left:2px solid #2963a3;border-radius:3px}.mini-precision .theme-mini-heading{position:absolute;left:5px;top:6px;width:29px;height:3px}.mini-precision .theme-mini-image{display:none}.mini-precision .theme-mini-line{height:2px;margin-bottom:3px}.mini-precision .theme-mini-link{height:2px;margin-top:3px;width:25%}.feed-colors{border:0;padding:0;margin:0 0 20px}.feed-colors legend{font-size:13px;font-weight:600;margin-bottom:10px}.color-segments{display:inline-flex;padding:3px;gap:3px;border-radius:9px;background:#eef0f3}.color-segments label{position:relative;cursor:pointer}.color-segments input{position:absolute;opacity:0;width:1px;height:1px}.color-segments span{display:block;padding:6px 16px;border-radius:6px;font-size:12px;color:#5b6c7e}.color-segments input:checked+span{background:white;color:#172536;box-shadow:0 1px 4px #0002}.color-segments input:focus-visible+span{outline:2px solid #007aff}.color-segments input:disabled+span{opacity:.6}
</style>'''


PRECISION_LAYOUT='''
.news-theme-precision .news-page{grid-template-columns:minmax(0,1fr);gap:12px}.news-theme-precision .news-card{display:grid;grid-template-columns:165px minmax(0,1fr) 76px;align-items:start;gap:20px;padding:18px!important;border-top:1px solid #d8e2ed!important;border-left:3px solid var(--theme-link)!important;border-radius:6px!important;box-shadow:none}.news-theme-precision .news-publisher{border:0;padding:0;margin:3px 0}.news-theme-precision .news-post{display:flex;align-items:flex-start;gap:16px;background:transparent}.news-theme-precision .news-media{width:112px;aspect-ratio:1;flex:none;border-radius:4px}.news-theme-precision .news-inner{flex:1;min-width:0;min-height:0!important;padding:0}.news-theme-precision .news-author{margin:0 0 8px}.news-theme-precision .news-actions{justify-content:flex-end;flex-wrap:wrap;gap:12px;border:0;padding:3px 0;margin:0}.news-theme-precision .news-share{width:100%;justify-content:flex-end}.news-theme-precision .news-other-sources{grid-column:2;margin:0;font-size:12px}.news-theme-precision .news-card>.news-publisher{grid-column:1;grid-row:1}.news-theme-precision .news-card>.news-post{grid-column:2;grid-row:1}.news-theme-precision .news-card>.news-actions{grid-column:3;grid-row:1}.news-theme-precision .news-card>.content{grid-column:2;grid-row:1;margin:0!important}.news-theme-precision .news-card:has(>.content)>.news-post{grid-row:2}.news-theme-precision .news-dots{margin-top:18px}.news-theme-precision .news-arrow{top:auto;bottom:22px}.news-theme-precision .news-stream-list .news-card{display:block;border-left:0!important}.news-theme-precision .news-stream-list .news-publisher{padding-bottom:12px;margin-bottom:12px}.news-theme-precision .news-stream-list .news-post{display:block}.news-theme-precision .news-stream-list .news-media{width:100%;aspect-ratio:auto}.news-theme-precision .news-stream-list .news-inner{padding:16px 0}.news-theme-precision .news-stream-list .news-actions{justify-content:flex-start;flex-wrap:nowrap}.news-theme-precision .news-stream-list .news-share{width:auto}
@media(max-width:650px){.news-theme-precision .news-card{grid-template-columns:minmax(0,1fr) auto;gap:12px;padding:14px!important}.news-theme-precision .news-publisher{grid-column:1}.news-theme-precision .news-card>.news-post{grid-column:1/-1;grid-row:2;gap:12px}.news-theme-precision .news-card>.content{grid-column:1/-1;grid-row:2}.news-theme-precision .news-card:has(>.content)>.news-post{grid-row:3}.news-theme-precision .news-media{width:88px}.news-theme-precision .news-card>.news-actions{grid-column:2;grid-row:1}.news-theme-precision .news-actions .news-share{width:auto}.news-theme-precision .news-actions .news-share span{display:none}}
'''


def palette(style,accent,color_theme):
    scope='.news-theme-'+style
    # Preserve each layout's original palette unless the user selects an override.
    dark=color_theme=='dark' or (color_theme=='auto' and style=='slate')
    link='color-mix(in srgb,'+accent+',white 50%)' if dark else accent
    css=scope+'{--theme-link:'+link+'}'+scope+' .news-body-link,'+scope+' .news-tag,'+scope+' [data-read-more]{color:var(--theme-link)}'
    if color_theme=='auto':return css
    background,card,inner,border,text,muted=('#101c2b','#1a293b','#142233','#314359','#edf3fc','#b3c3d6') if dark else ('#ffffff','#f7f9fc','#eef2f6','#d8e2ed','#172c46','#65788d')
    rules={
        '':'background:'+background+';color:'+text+';color-scheme:'+('dark' if dark else 'light'),
        ' .news-card':'background:'+card+';border-color:'+border+'!important',
        ' .news-post':'background:'+inner+';border-color:'+border,
        ' .news-media':'background:'+inner,
        ' .news-name':'color:'+text,
        ' .content':'color:'+text,
        ' .news-date':'color:'+muted,
        ' .news-actions':'color:'+muted+';border-color:'+border,
        ' .news-avatar':'background:'+border+';color:'+muted,
        ' .news-publisher':'border-color:'+border,
        ' .news-dots button[aria-current=page]':'background:var(--theme-link)',
        ' .news-stream-list .news-card':'border-bottom-color:'+background+'!important',
    }
    return css+''.join(scope+selector+'{'+properties+'}' for selector,properties in rules.items())+(scope+' .news-card{border-left-color:var(--theme-link)!important}' if style=='precision' else '')
