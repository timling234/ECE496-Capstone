"""Shared feed styles and instant-save appearance picker."""
THEMES={
    'classic':('Classic','Familiar social cards'),
    'precision':('Precision','Scrollable research briefing'),
    'classic_dark':('Classic Dark','Social cards · dark'),
    'precision_dark':('Precision Dark','Scrollable briefing · dark'),
}


def selector(selected='classic'):
    cards=[]
    for key,(name,description) in THEMES.items():
        mini=''.join('<span class="theme-mini-card"><i class="theme-mini-heading"></i>'+('<i class="theme-mini-image"></i>' if i!=1 else '')+'<i class="theme-mini-line"></i><i class="theme-mini-line short"></i><i class="theme-mini-link"></i></span>' for i in range(3))
        preview='mini-'+('precision' if key.startswith('precision') else 'classic')+(' mini-dark' if key.endswith('_dark') else '')
        cards.append('<label class="theme-option"><input type="radio" name="style" value="'+key+'" '+('checked ' if selected==key else '')+'><span class="theme-thumbnail '+preview+'" aria-hidden="true">'+mini+'<span class="theme-check">✓</span></span><span class="theme-title">'+name+'</span><span class="theme-description">'+description+'</span></label>')
    return PICKER_STYLE+PRECISION_PICKER+'<fieldset class="theme-picker"><legend>Feed style</legend><div class="theme-options">'+''.join(cards)+'</div></fieldset><p class="theme-hint">Changes save automatically and apply to your embedded feed and Mock Website.</p>'


PICKER_STYLE='''<style>
.theme-picker{border:0;padding:0;margin:0 0 12px;max-width:860px}.theme-picker legend{font-size:13px;font-weight:600;margin-bottom:12px}.theme-options{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;background:#f5f5f7;padding:16px;border:1px solid #e7e8ec;border-radius:18px}.theme-option{position:relative;cursor:pointer;min-width:0}.theme-option>input{position:absolute;opacity:0;width:1px;height:1px}.theme-thumbnail{position:relative;display:flex;align-items:flex-start;gap:7px;height:132px;box-sizing:border-box;padding:14px 10px;background:white;border:2px solid transparent;border-radius:12px;box-shadow:0 2px 8px #17253612;overflow:hidden;transition:border-color .15s,box-shadow .15s}.theme-option:has(input:checked) .theme-thumbnail{border-color:#007aff;box-shadow:0 0 0 3px #007aff18}.theme-option:has(input:focus-visible) .theme-thumbnail{outline:3px solid #007aff;outline-offset:3px}.theme-option:has(input:disabled){cursor:wait;opacity:.7}.theme-title{display:block;text-align:center;font-size:13px;font-weight:600;margin-top:10px;color:#1d2530}.theme-description{display:block;text-align:center;font-size:11px;color:#6b7280;margin-top:4px}.theme-check{position:absolute;right:6px;bottom:6px;display:none;width:20px;height:20px;text-align:center;line-height:20px;border-radius:50%;background:#007aff;color:white;font-size:13px;font-weight:700}.theme-option:has(input:checked) .theme-check{display:block}.theme-mini-card{flex:1;min-width:0;padding:7px 5px;background:#f7f7f7;border-radius:4px}.theme-mini-card i{display:block}.theme-mini-heading{height:4px;width:80%;background:#7c8794;margin-bottom:7px;border-radius:2px}.theme-mini-image{height:37px;background:linear-gradient(135deg,#d5e2ec,#96aec4);margin-bottom:7px;border-radius:2px}.theme-mini-line{height:3px;background:#bac2cb;margin-bottom:4px}.theme-mini-line.short{width:65%}.theme-mini-link{height:3px;background:#4596f0;width:42%;margin-top:7px}.mini-precision .theme-mini-card{background:white;border:1px solid #dbe2eb;border-top:2px solid #2963a3;border-radius:1px}.mini-precision .theme-mini-image{height:31px;border-radius:0;background:linear-gradient(140deg,#dce5ee,#adc2d9)}.mini-dark{background:#101c2b}.mini-dark .theme-mini-card{background:#1c2b3d;border:1px solid #314358}.mini-dark .theme-mini-heading{background:#c6d3e2}.mini-dark .theme-mini-line{background:#60758c}.mini-dark .theme-mini-image{background:linear-gradient(140deg,#334d65,#658ba7)}.mini-dark .theme-mini-link{background:#80beff}.theme-hint{font-size:12px;color:#667588;margin:0 0 18px}@media(max-width:600px){.theme-options{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding:10px}.theme-thumbnail{height:100px;padding:10px 5px;gap:4px}.theme-mini-card{padding:4px 3px}.theme-mini-image{height:24px}.theme-description{display:none}}
</style>'''


def theme_css(style,accent,settings=None):
    import re
    settings=settings or {}
    if not re.fullmatch(r'#[0-9a-fA-F]{6}',accent):accent='#215e95'
    base='precision' if style.startswith('precision') else 'classic'
    css=(PRECISION_BASE+PRECISION_LAYOUT).replace('news-theme-precision','news-theme-'+style) if base=='precision' else ''
    css+=palette(style,accent,'dark' if style.endswith('_dark') else 'auto')
    scope='.news-theme-'+style
    for prefix,selectors in [('text',(' .content',)),('title',(' .news-name',' .content h1',' .content h2',' .content h3'))]:
        rules=[]
        color=settings.get(prefix+'_color','')
        if re.fullmatch(r'#[0-9a-fA-F]{6}',color):rules.append('color:'+color)
        font=FONTS.get(settings.get(prefix+'_font','default'))
        if font:rules.append('font-family:'+font)
        if prefix=='title':rules.append('font-size:'+str(settings.get('title_size',13))+'px')
        if rules:css+=','.join(scope+selector for selector in selectors)+'{'+(';'.join(rules))+'}'
    link_font=FONTS.get(settings.get('link_font','default')) or (FONTS['system'] if base=='precision' else 'Arial,system-ui,sans-serif')
    rules='font-family:'+link_font+';font-size:'+str(settings.get('link_size',settings.get('font_size',16)))+'px'
    css+=','.join(scope+selector for selector in (' .news-body-link',' .news-tag',' [data-read-more]',' .news-share'))+'{'+rules+'}'
    return '<style>'+css+'</style>'


PRECISION_BASE='.news-theme-precision{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.news-theme-precision .news-page{gap:20px}.news-theme-precision .news-card{background:white;border:1px solid #d8e2ed!important;border-top:3px solid var(--theme-link)!important;border-radius:4px!important;padding:18px!important;box-shadow:0 3px 12px #152e4b08}.news-theme-precision .news-publisher{padding-bottom:13px;border-bottom:1px solid #e5ebf1}.news-theme-precision .news-name{color:#172c46;font-weight:650}.news-theme-precision .news-date{font:11px ui-monospace,SFMono-Regular,Consolas,monospace;color:#65788d;margin-top:5px}.news-theme-precision .news-post{background:#fafcfe;border:0;border-radius:0}.news-theme-precision .news-inner{padding:14px 0}.news-theme-precision .content{color:#283c52;line-height:1.5}.news-theme-precision .content.collapsed{max-height:4.5em}.news-theme-precision .news-actions{border-top:1px solid #e5ebf1;padding-top:14px;color:#5b6f85}.news-theme-precision .news-media{background:#eaf0f6}.news-theme-precision .news-dots button[aria-current=page]{background:var(--theme-link)}.news-theme-precision .news-arrow{background:#274766e8}.news-theme-precision .news-stream-list .news-card{border-top:0!important;border-bottom:8px solid #eaf0f6!important;border-radius:0!important}'

PRECISION_PICKER='''<style>
.mini-precision{flex-direction:column;gap:6px}.mini-precision .theme-mini-card{position:relative;flex:none;display:block;width:100%;height:28px;box-sizing:border-box;padding:5px 8px 3px 45px;border:1px solid #dbe2eb;border-left:2px solid #2963a3;border-radius:3px}.mini-precision.mini-dark .theme-mini-card{background:#1c2b3d;border-color:#314358}.mini-precision .theme-mini-heading{position:absolute;left:5px;top:6px;width:29px;height:3px}.mini-precision .theme-mini-image{display:none}.mini-precision .theme-mini-line{height:2px;margin-bottom:3px}.mini-precision .theme-mini-link{height:2px;margin-top:3px;width:25%}@media(max-width:600px){.theme-options{grid-template-columns:repeat(2,minmax(0,1fr))}}.feed-type-grid{display:grid;grid-template-columns:90px minmax(90px,140px) minmax(140px,240px) 100px;gap:12px;align-items:center;margin:20px 0}.feed-type-grid label{font-size:13px}.feed-type-grid select{display:block;width:100%;padding:6px;margin-top:4px}.feed-type-grid input[type=number]{display:block;margin-top:4px;width:100%}.feed-type-grid input[type=color]{display:block;width:52px;height:30px;padding:2px;margin-top:4px}.feed-icon-toggle{display:block;margin:18px 0 8px}.feed-type-grid button{justify-self:start}@media(max-width:650px){.feed-type-grid{grid-template-columns:1fr 1fr}.feed-type-grid>b{grid-column:1/-1}}

</style>'''


PRECISION_LAYOUT='''
.news-carousel.news-theme-precision:not(.news-stream-mode){height:620px;overflow:hidden;border:1px solid #d8e2ed;border-radius:10px;padding:12px;box-sizing:border-box}.news-carousel.news-theme-precision:not(.news-stream-mode)>.news-pages{height:100%;overflow-y:auto;overscroll-behavior:contain;scrollbar-gutter:stable;padding-right:4px;box-sizing:border-box}.news-carousel.news-theme-precision:not(.news-stream-mode)>.news-dots,.news-carousel.news-theme-precision:not(.news-stream-mode)>.news-arrow{display:none!important}
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
    return css+''.join(scope+selector+'{'+properties+'}' for selector,properties in rules.items())+(scope+' .news-card{border-left-color:var(--theme-link)!important}' if style.startswith('precision') else '')

FONTS={
    'default':None,
    'system':'-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif',
    'arial':'Arial,Helvetica,sans-serif',
    'georgia':'Georgia,"Times New Roman",serif',
    'times':'"Times New Roman",Times,serif',
    'mono':'ui-monospace,SFMono-Regular,Consolas,monospace',
}


def typography_controls(settings):
    from html import escape
    dark=settings.get('style','classic').endswith('_dark')
    body=['<div class="feed-type-grid">']
    for prefix,label,size_name,default_size in [('title','Title','title_size',13),('text','Body','font_size',16),('link','Link','link_size',16)]:
        default=('#edf3fc' if dark else '#151515') if prefix=='title' else ('#dee7f2' if dark else '#222222')
        color=settings.get(prefix+'_color') or default
        color_name=prefix+'_color'
        marker='<input type="hidden" name="'+prefix+'_color_custom" value="'+('1' if settings.get(prefix+'_color') else '0')+'">'
        custom=' data-custom-color="'+prefix+'"'
        if prefix=='link':color=settings['accent'];color_name='accent';marker=custom=''
        choices=''.join('<option value="'+key+'" '+('selected' if settings.get(prefix+'_font','default')==key else '')+'>'+name+'</option>' for key,name in [('default','Style default'),('system','System'),('arial','Arial'),('georgia','Georgia'),('times','Times New Roman'),('mono','Monospace')])
        body.append('<b>'+label+'</b><label>Text color<input aria-label="'+label+' text color" type="color" name="'+color_name+'" value="'+escape(color,quote=True)+'"'+custom+'>'+marker+'</label><label>Text font<select aria-label="'+label+' text font" name="'+prefix+'_font">'+choices+'</select></label><label>Font size<input aria-label="'+label+' font size" type="number" name="'+size_name+'" value="'+str(settings.get(size_name,default_size))+'" min="12" max="24"></label>')
    return ''.join(body)+'</div><button type="button" data-reset-text-colors>Reset typography</button>'
