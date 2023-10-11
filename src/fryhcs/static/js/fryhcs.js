let activeEffectStack = [];

class Signal {
    constructor(rawValue) {
        this.rawValue = rawValue;
        this.effectSet = new Set();
    }

    addEffect(effect) {
        this.effectSet.add(effect);
    }

    removeEffect(effect) {
        this.effectSet.delete(effect);
    }

    hasEffect(effect) {
        return this.effectSet.has(effect);
    }

    peek() {
        return this.rawValue;
    }

    get value() {
        const len = activeEffectStack.length;
        if (len === 0) {
            return this.rawValue;
        }
        const currentEffect = activeEffectStack[len-1];
        if (!this.hasEffect(currentEffect)) {
            this.effectSet.add(currentEffect);
            currentEffect.addSignal(this);
        }
        return this.rawValue;
    }

    set value(rawValue) {
        if (this.rawValue !== rawValue) {
            this.rawValue = rawValue;
            const errs = [];
            for (const effect of this.effectSet) {
                try {
                    effect.callback();
                } catch (err) {
                    errs.push([effect, err]);
                }
            }
            if (errs.length > 0) {
                throw errs;
            }
        }
    }
}

function signal(rawValue) {
    return new Signal(rawValue);
}


class Effect {
    constructor(fn) {
        this.fn = fn;
        this.active = false;
        this.todispose = false;
        this.disposed = false;
        this.signalSet = new Set();
    }

    addSignal(signal) {
        this.signalSet.add(signal);
    }

    removeSignal(signal) {
        this.signalSet.delete(signal);
    }

    callback() {
        if (this.active === true || this.disposed === true) {
            return;
        }
        activeEffectStack.push(this);
        this.active = true;
        this.signalSet.clear();
        try {
            this.fn();
        } finally {
            this.active = false;
            activeEffectStack.pop();
            if (this.todispose) {
                this.dispose();
            }
        }
    }

    dispose() {
        if (this.disposed) {
            return;
        }
        if (this.active) {
            this.todispose = true;
            return;
        }
        for (const signal of this.signalSet) {
            signal.removeEffect(this);
        }
        this.signalSet.clear();
        this.todispose = false;
        this.disposed = true;
    }
}

function effect(fn) {
    const e = new Effect(fn);
    try {
        e.callback();
    } catch (err) {
        e.dispose();
        throw err;
    }
    return e.dispose.bind(e);
}


function hydrate(rootElement, componentId, embedValues) {
    const prefix = '' + componentId + '/';
    function handle(element) {
        if ('fryembed' in element.dataset) {
            const embeds = element.dataset.fryembed;
            for (const embed of embeds.split(' ')) {
                if (!embed.startsWith(prefix)) {
                    continue;
                }
                const [embedId, atype, ...args] = embed.substr(prefix.length).split('-');
                const index = parseInt(embedId);
                const arg = args.join('-')
                if (index >= embedValues.length) {
                    console.log("invalid embed id: ", embedId);
                    continue;
                }
                const value = embedValues[index];

                if (atype === 'text') {
                    // 设置html文本时需要进行响应式处理
                    if (value instanceof Signal) {
                        effect(() => element.textContent = value.value);
                    } else {
                        element.textContent = value;
                    }
                } else if (atype === 'event') {
                    element.addEventListener(arg, value);
                } else if (atype === 'attr') {
                    // 设置html元素属性值时需要进行响应式处理
                    if (value instanceof Signal) {
                        effect(() => element.setAttribute(arg, value.value));
                    } else {
                        element.setAttribute(arg, value);
                    }
                } else if (atype === 'object') {
                    // 设置对象属性时不使用effect，signal对象本身将传给js脚本
                    if (!('frydata' in element)) {
                        element.frydata = {};
                    }
                    element.frydata[arg] = value;
                } else {
                    console.log("invalid attribute type: ", atype);
                }
            }
        }
        for (const child of element.children) {
            handle(child);
        }
    }
    handle(rootElement);
}


function update(components, props, options) {
}


const default_options = {
    bubbles: false,
    cancelable: false,
    composed: false,
}

function event(component, type, options) {
    const elements = document.querySelectorAll(`[data-fryclass~="${component}"]`);
    if (elements.length == 0) {
        return;
    }
    let opts = {};
    for (const option in options) {
        const value = options[option];
        if (option in default_options) {
            opts[option] = value;
        } else {
            if (!('detail' in opts)) {
                opts['detail'] = {};
            }
            opts['detail'][option] = value;
        }
    }
    let ev;
    if ('detail' in opts) {
        ev = new CustomEvent(type, opts);
    } else {
        ev = new Event(type, opts);
    }
    for (const element of elements) {
        element.dispatchEvent(ev);
    }
}


export {signal, effect, hydrate, update, event}
