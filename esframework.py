

class CF(object):
    true = 1.0
    false = -1.0
    unknown = 0.0
    cutoff = 0.1 # We will consider values above cutoff to be True.



def cf_or(a, b):
    if a > 0 and b > 0:
        return a + b - a * b
    elif a < 0 and b < 0:
        return a + b + a * b
    else:
        return (a + b)

def cf_and(a, b):
    return a*b

def is_cf(x):
    return CF.false <= x <= CF.true

def cf_true(x):
    return is_cf(x) and x > CF.cutoff

def cf_false(x):
    return is_cf(x) and x < (CF.cutoff - 1)

class Context(object):
    
    
    def __init__(self, name, initial_data=None, goals=None):
        self.count = 0 # track Instances with numerical IDs
        self.name = name
        self.initial_data = initial_data or [] # params to find out before reasoning
        self.goals = goals or [] # params to find out during reasoning
    
    def instantiate(self):
        inst = (self.name, self.count)
        self.count += 1
        return inst


class Parameter(object):
    
    def __init__(self, name, ctx=None, enum=None, cls=None, ask_first=False):

        self.name = name
        self.ctx = ctx
        self.enum = enum
        self.ask_first = ask_first
        self.cls = cls
        
    def type_string(self):
        return self.cls.__name__ if self.cls else '(%s)' % ', '.join(list(self.enum))
    
    def from_string(self, val):

        if self.cls:
            return self.cls(val)
        if self.enum and val in self.enum:
            return val
        
        raise ValueError('val must be one of %s for the parameter %s' % (', '.join(list(self.enum)), self.name))



def eval_condition(condition, values, find_out=None):

    param, inst, op, val = condition
    if find_out:
        find_out(param, inst) # get more values for this param
    total = CF.unknown
    for known_val,cf in values.items():
        if op(known_val,val):
            total = cf_or(total,cf)
    return total

def print_condition(condition):

    param, inst, op, val = condition
    name = inst if isinstance(inst, str) else inst[0]
    opname = op.__name__
    return '%s %s %s %s' % (param, name, opname, val)


def get_vals(values, param, inst):

    return values.setdefault((param, inst), {})

def get_cf(values, param, inst, val):

    vals = get_vals(values, param, inst)
    return vals.setdefault(val, CF.unknown)

def update_cf(values, param, inst, val, cf):

    existing = get_cf(values, param, inst, val)
    updated = cf_or(existing, cf)
    get_vals(values, param, inst)[val] = updated
    

class Rule(object):

    
    def __init__(self, num, premises, conclusions, cf):
        self.num = num
        self.cf = cf

        self.raw_premises = premises 
        self.raw_conclusions = conclusions
    
    def __str__(self):
        prems = map(print_condition, self.raw_premises)
        concls = map(print_condition, self.raw_conclusions)
        templ = 'RULE %d states\nIF\n\t%s\nTHEN %f\n\t%s'
        return templ % (self.num, '\n\t'.join(prems), self.cf, '\n\t'.join(concls))
    
    def clone(self):

        return Rule(self.num, list(self.raw_premises),
                    list(self.raw_conclusions), self.cf)
    
    def _bind_cond(self, cond, instances):

        param, ctx, op, val = cond
        return param, instances[ctx], op, val
        
    def premises(self, instances):

        return [self._bind_cond(premise, instances) for premise in self.raw_premises]
    
    def conclusions(self, instances):

        return [self._bind_cond(concl, instances) for concl in self.raw_conclusions]

    def applicable(self, values, instances, find_out=None):


        for premise in self.premises(instances):
            param, inst, op, val = premise
            vals = get_vals(values, param, inst)
            cf = eval_condition(premise, vals) # don't pass find_out, just use rules
            if cf_false(cf):
                return CF.false
        total_cf = CF.true
        for premise in self.premises(instances):
            param, inst, op, val = premise
            vals = get_vals(values, param, inst)
            cf = eval_condition(premise, vals, find_out)
            total_cf = cf_and(total_cf, cf)
            if not cf_true(total_cf):
                return CF.false
        return total_cf

    
    def apply(self, values, instances, find_out=None, track=None):
    
        
        if track:
            track(self)
        
        cf = self.cf * self.applicable(values, instances, find_out)
        if not cf_true(cf):
            return False
        
        for conclusion in self.conclusions(instances):
            param, inst, op, val = conclusion
            update_cf(values, param, inst, val, cf)
        
        return True

def use_rules(values, instances, rules, find_out=None, track_rules=None):
    return any([rule.apply(values, instances, find_out, track_rules) for rule in rules])




class Shell(object):
    
    
    def __init__(self, read=input, write=print):
 
        self.read = read
        self.write = write
        self.rules = {} # index rules under each param in the conclusions
        self.contexts = {} # indexed by name
        self.params = {} # indexed by name
        self.known = set() # (param, inst) pairs that have already been determined
        self.asked = set() # (param, inst) pairs that have already been asked
        self.known_values = {} # dict mapping (param, inst) to a list of (val, cf) pairs
        self.current_inst = None # the instance under consideration
        self.instances = {} # dict mapping ctx_name -> most recent instance of ctx
        self.current_rule = None # track the current rule for introspection
    
    def clear(self):
        self.known.clear()
        self.asked.clear()
        self.known_values.clear()
        self.current_inst = None
        self.current_rule = None
        self.instances.clear()
    
    def define_rule(self, rule):
        for param, ctx, op, val in rule.raw_conclusions:
            self.rules.setdefault(param, []).append(rule)
    
    def define_context(self, ctx):
        self.contexts[ctx.name] = ctx
        
    def define_param(self, param):
        self.params[param.name] = param
    
    def get_rules(self, param):
        return self.rules.setdefault(param, [])
    
    def instantiate(self, ctx_name):
        inst = self.contexts[ctx_name].instantiate()
        self.current_inst = inst
        self.instances[ctx_name] = inst
        return inst
    
    def get_param(self, name):
        return self.params.setdefault(name, Parameter(name))
   
    HELP = """Type one of the following:
?       - to see possible answers for this parameter
rule    - to show the current rule
why     - to see why this question is asked
help    - to show this message
unknown - if the answer to this question is not known
<val>   - a single definite answer to the question
<val1> <cf1> [, <val2> <cf2>, ...]
        - if there are multiple answers with associated certainty factors."""

    def ask_values(self, param, inst):
        
        if (param, inst) in self.asked:
            return
        self.asked.add((param, inst))
        while True:
            resp = self.read('What is the %s of %s-%d? ' % (param, inst[0], inst[1]))
            if not resp:
                continue
            if resp == 'unknown':
                return False
            elif resp == 'help':
                self.write(Shell.HELP)
                
        
            elif resp == 'why':
                self.print_why(param)
            elif resp == 'rule':
                self.write(self.current_rule)
            elif resp == '?':
                self.write('%s must be of type %s' %
                           (param, self.get_param(param).type_string()))
            
            # Read the value and store it.
            else:
                try:
                    for val, cf in parse_reply(self.get_param(param), resp):
                        update_cf(self.known_values, param, inst, val, cf)
                    return True
                except:
                    self.write('Invalid response. Type ? to see legal ones.')
    
    def print_why(self, param):
     
        self.write('Why is the value of %s being asked for?' % param)
        if self.current_rule in ('initial', 'goal'):
            self.write('%s is one of the %s parameters.' % (param, self.current_rule))
            return

        known, unknown = [], []
        for premise in self.current_rule.premises(self.instances):
            vals = get_vals(self.known_values, premise[0], premise[1])
            if cf_true(eval_condition(premise, vals)):
                known.append(premise)
            else:
                unknown.append(premise)
        
        if known:
            self.write('It is known that:')
            for condition in known:
                self.write(print_condition(condition))
            self.write('Therefore,')
        
        rule = self.current_rule.clone()
        rule.raw_premises = unknown
        self.write(rule)
    
    def _set_current_rule(self, rule):
        self.current_rule = rule
    
    
    def find_out(self, param, inst=None):

        inst = inst or self.current_inst
        
        if (param, inst) in self.known: 
            return True

        def rules():
            return use_rules(self.known_values, self.instances,
                             self.get_rules(param), self.find_out,
                             self._set_current_rule)
        if self.get_param(param).ask_first:
            success = self.ask_values(param, inst) or rules()
        else:
            success = rules() or self.ask_values(param, inst)
        if success:
            self.known.add((param, inst)) # Remember that we already know this value
        return success

    def execute(self, context_names):

        
        self.write('Beginning execution. For help answering questions, type "help".')
        self.clear()
        results = {}
        for name in context_names:
            ctx = self.contexts[name]
            self.instantiate(name)
            
            # Gather initial data.  This stage is one of the features that
            # differentiates Emycin from Prolog: the user can specify that some
            # data should be collected before reasoning about the goals takes
            # place.
            self._set_current_rule('initial')
            for param in ctx.initial_data:
                self.find_out(param)
            
            # Try to collect all of the goal data.
            self._set_current_rule('goal')
            for param in ctx.goals:
                self.find_out(param)
            
            # Record findings.
            if ctx.goals:
                result = {}
                for param in ctx.goals:
                    result[param] = get_vals(self.known_values, param, self.current_inst)
                results[self.current_inst] = result
            
        return results

def parse_reply(param, reply):

    if reply.find(',') >= 0:
        vals = []
        for pair in reply.split(','):
            val, cf = pair.strip().split(' ')
            vals.append((param.from_string(val), float(cf)))
        return vals
    return [(param.from_string(reply), CF.true)]




