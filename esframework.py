

class CF(object):
    """Collect important certainty factors in a single namespace."""
    true = 1.0
    false = -1.0
    unknown = 0.0
    cutoff = 0.1 # We will consider values above cutoff to be True.



def cf_or(a, b):
    """The OR of two certainty factors."""
    if a > 0 and b > 0:
        return a + b - a * b
    elif a < 0 and b < 0:
        return a + b + a * b
    else:
        return (a + b)

def cf_and(a, b):
    """The AND of two certainty factors."""
    return min(a, b)

def is_cf(x):
    """Is x a valid certainty factor; ie, is (false <= x <= true)?"""
    return CF.false <= x <= CF.true

def cf_true(x):
    """Do we consider x true?"""
    return is_cf(x) and x > CF.cutoff

def cf_false(x):
    """Do we consider x false?"""
    return is_cf(x) and x < (CF.cutoff - 1)

class Context(object):
    
    """A Context is a type of thing that can be reasoned about."""
    
    def __init__(self, name, initial_data=None, goals=None):
        self.count = 0 # track Instances with numerical IDs
        self.name = name
        self.initial_data = initial_data or [] # params to find out before reasoning
        self.goals = goals or [] # params to find out during reasoning
    
    def instantiate(self):
        """Instances are represented in the form (ctx_name, inst_number)."""
        inst = (self.name, self.count)
        self.count += 1
        return inst


class Parameter(object):
    
    """A Parameter represents an attribute of a context."""
    
    def __init__(self, name, ctx=None, enum=None, cls=None, ask_first=False):

        self.name = name
        self.ctx = ctx
        self.enum = enum
        self.ask_first = ask_first
        self.cls = cls
        
    def type_string(self):
        """A human-readable string of acceptable values for this parameter."""
        return self.cls.__name__ if self.cls else '(%s)' % ', '.join(list(self.enum))
    
    def from_string(self, val):
        """
        Read a value of this parameter with the correct type from a
        user-specified string.
        """
        if self.cls:
            return self.cls(val)
        if self.enum and val in self.enum:
            return val
        
        raise ValueError('val must be one of %s for the parameter %s' % (', '.join(list(self.enum)), self.name))



def eval_condition(condition, values, find_out=None):
    """
    To determine the certainty factor of the condition (param, inst, op, val)
    """
    param, inst, op, val = condition
    if find_out:
        find_out(param, inst) # get more values for this param
    total = CF.unknown
    for known_val,cf in values.items():
        if op(known_val,val):
            total = cf_or(total,cf)
    return total

def print_condition(condition):
    """Return a human-readable representation of a condition."""
    param, inst, op, val = condition
    name = inst if isinstance(inst, str) else inst[0]
    opname = op.__name__
    return '%s %s %s %s' % (param, name, opname, val)


def get_vals(values, param, inst):
    """Retrieve the dict of val->CF mappings for (param, inst)."""
    return values.setdefault((param, inst), {})

def get_cf(values, param, inst, val):
    """Retrieve the certainty that the value of the parameter param in inst is val."""
    vals = get_vals(values, param, inst)
    return vals.setdefault(val, CF.unknown)

def update_cf(values, param, inst, val, cf):
    """
    Update the existing certainty that the value of the param parameter of inst
    is val with the specified certainty factor.  If val is not currently a value
    associated with param in inst, add it.  The OR operation is used to combine
    the existing and new certainty factors.
    """
    existing = get_cf(values, param, inst, val)
    updated = cf_or(existing, cf)
    get_vals(values, param, inst)[val] = updated
    

class Rule(object):
    
    """
    Rules are used for deriving new facts.  Each rule has premise and conclusion
    conditions and an associated certainty of the derived conclusions.
    """
    
    def __init__(self, num, premises, conclusions, cf):
        self.num = num
        self.cf = cf
        # The premise conditions for a rule are stored with context names in the
        # place of instances for generality; ie, (param, ctx_name, op, val).
        self.raw_premises = premises 
        self.raw_conclusions = conclusions
    
    def __str__(self):
        prems = map(print_condition, self.raw_premises)
        concls = map(print_condition, self.raw_conclusions)
        templ = 'RULE %d\nIF\n\t%s\nTHEN %f\n\t%s'
        return templ % (self.num, '\n\t'.join(prems), self.cf, '\n\t'.join(concls))
    
    def clone(self):
        """Duplicate this rule."""
        return Rule(self.num, list(self.raw_premises),
                    list(self.raw_conclusions), self.cf)
    
    def _bind_cond(self, cond, instances):
        """
        Given a condition (param, ctx, op, val), return (param, inst, op, val),
        where inst is the current instance of the context ctx.
        """
        param, ctx, op, val = cond
        return param, instances[ctx], op, val
        
    def premises(self, instances):
        """Return the premise conditions of this rule."""
        return [self._bind_cond(premise, instances) for premise in self.raw_premises]
    
    def conclusions(self, instances):
        """Return the conclusion conditions of this rule."""
        return [self._bind_cond(concl, instances) for concl in self.raw_conclusions]

    def applicable(self, values, instances, find_out=None):
        """
        **applicable** determines the applicability of this rule (represented by
        a certainty factor) by evaluating the truth of each of its premise
        conditions against known values of parameters.
        
        This function is key to the backwards-chaining reasoning algorithm:
        after a candidate rule is identified by the reasoner (see
        [Shell.find_out](#find_out)), it tries to satisfy all the premises of
        the rule.  This is similar to Prolog, where a rule can only be applied
        if all its body goals can be achieved.
        
        Arguments:
        
        - values: a dict that maps a (param, inst) pair to a list of known
          values [(val1, cf1), (val2, cf2), ...] associated with that pair.
          param is the name of a Parameter object and inst is the name of a
          Context.
        - instances: a dict that maps a Context name to its current instance.
        - find_out: see eval_condition
        
        """
        # Try to reject the rule early if possible by checking each premise
        # without reasoning.
        for premise in self.premises(instances):
            param, inst, op, val = premise
            vals = get_vals(values, param, inst)
            cf = eval_condition(premise, vals) # don't pass find_out, just use rules
            if cf_false(cf):
                return CF.false
        # Evaluate each premise (calling find_out to apply reasoning) to
        # determine if the rule can be applied.
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
        """
        **apply** tries to use this rule by first determining if it is
        applicable (see [Rule.applicable](#applicable)), and if so, combining
        the conclusions with known values to deduce new values.  Returns True if
        this rule applied successfully and False otherwise.
        """
        
        if track:
            track(self)
        
        # Test the applicability of the rule (the AND of all its premises).
        cf = self.cf * self.applicable(values, instances, find_out)
        if not cf_true(cf):
            return False
        
        # Use each conclusion to derive new values and update certainty factors.
        for conclusion in self.conclusions(instances):
            param, inst, op, val = conclusion
            update_cf(values, param, inst, val, cf)
        
        return True

### Using the rules

def use_rules(values, instances, rules, find_out=None, track_rules=None):
    """Apply rules to derive new facts; returns True if any rule succeeded."""
    
    # Note that we can't simply iterate over the rules and try applying them
    # until one succeeds in finding new values--we have to apply them all,
    # because any of them could decrease the certainty of a condition, and stopping
    # early could lead to fault conclusions.  This differs from Prolog, where
    # only new truths are deduced.
    
    return any([rule.apply(values, instances, find_out, track_rules) for rule in rules])




class Shell(object):
    
    """An expert system shell."""
    
    def __init__(self, read=input, write=print):
        """
        Create a new shell.  The functions read and write are used to get
        input from the user and display information, respectively.
        """
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
        """Clear per-problem state."""
        self.known.clear()
        self.asked.clear()
        self.known_values.clear()
        self.current_inst = None
        self.current_rule = None
        self.instances.clear()
    
    def define_rule(self, rule):
        """Define a rule."""
        for param, ctx, op, val in rule.raw_conclusions:
            self.rules.setdefault(param, []).append(rule)
    
    def define_context(self, ctx):
        """Define a context."""
        self.contexts[ctx.name] = ctx
        
    def define_param(self, param):
        """Define a parameter."""
        self.params[param.name] = param
    
    def get_rules(self, param):
        """Get all of the rules that can deduce values of the param parameter."""
        return self.rules.setdefault(param, [])
    
    def instantiate(self, ctx_name):
        """Create a new instance of the context with the given name."""
        inst = self.contexts[ctx_name].instantiate()
        self.current_inst = inst
        self.instances[ctx_name] = inst
        return inst
    
    def get_param(self, name):
        """
        Get the Parameter object with the given name.  Creates a new Parameter
        if one hasn't been defined previously.
        """
        return self.params.setdefault(name, Parameter(name))
    
    ### User input and introspection

    # Emycin interacts with users to gather information and print results.
    # While using the shell, the user will be asked questions to support reasoning,
    # and they have the option of asking the system what it is doing and why.  We
    # offer some support for user interaction:
    
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
        """Get values from the user for the param parameter of inst."""
        
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
                
            # The `why`, `rule`, and `?` commands allow the user to ask
            # Emycin why it is asking a question, which rule it is currently
            # applying, and what type of answer is expected from a question.
            # Together, these commands offer an introspection capability.
            
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
        """
        Explain to the user why a question is being asked; that is, show the
        rule that the reasoner is currently trying to apply.
        """
        self.write('Why is the value of %s being asked for?' % param)
        if self.current_rule in ('initial', 'goal'):
            self.write('%s is one of the %s parameters.' % (param, self.current_rule))
            return

        # Determine which premises are already satisfied and which are under
        # evaluation.  This explains why a question is being asked: to satisfy
        # one of the unsatisfied premises.
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
        """Track the rule under consideration for user introspection."""
        self.current_rule = rule
    
    ### Backwards-chaining
    
    # Our reasoner applies backwards-chaining to deduce new values for goal
    # parameters.  Given an instance and a parameter, it tries to find a value
    # for that parameter by finding all rules that can deduce that parameter
    # and trying to apply them.
    
    def find_out(self, param, inst=None):
        """
        Use rules and user input to determine possible values for (param, inst).
        Returns True if a value was found, and False otherwise.
        """
        inst = inst or self.current_inst

        if (param, inst) in self.known: # return early if we already know this value
            return True
        
        # To apply rules to find a value for the param parameter of inst, we
        # retrieve the rules that can deduce param values.  This is backwards
        # chaining: to reach a goal, we find rules that can satisfy that goal,
        # and try to apply them (see [Rule.apply](#apply)).  This function,
        # find_out, is used recursively by rule application to satisfy rule
        # premises.
        
        def rules():
            return use_rules(self.known_values, self.instances,
                             self.get_rules(param), self.find_out,
                             self._set_current_rule)

        # Some parameters are ask_first parameters, which means we should ask
        # the user for their values before applying rules.
        if self.get_param(param).ask_first:
            success = self.ask_values(param, inst) or rules()
        else:
            success = rules() or self.ask_values(param, inst)
        if success:
            self.known.add((param, inst)) # Remember that we already know this value
        return success

    def execute(self, context_names):
        """
        Gather the goal data for each named context and report the findings.
        The system attempts to gather the initial data specified for the context
        before attempting to gather the goal data.
        """
        
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
    """
    Returns a list of (value, cf) pairs for the Parameter param from a text
    reply.  Expected a single value (with an implicit CF of true) or a list of
    value/cf pairs val1 cf1, val2 cf2, ....
    """
    if reply.find(',') >= 0:
        vals = []
        for pair in reply.split(','):
            val, cf = pair.strip().split(' ')
            vals.append((param.from_string(val), float(cf)))
        return vals
    return [(param.from_string(reply), CF.true)]




