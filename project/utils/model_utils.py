# Repos.io / Copyright Stephane Angel / Creative Commons BY-NC-SA license

from django.db.models.sql.query import get_proxied_model
from django.db.models.query_utils import DeferredAttribute

from haystack.models import SearchResult

def get_app_and_model(instance):
    """
    Return the app_label and model_name for the given instance.
    Work for normal model instance but also a proxied one (think `only` and
    `defer`), and even for instance of SearchResult (haystack)
    """
    if isinstance(instance, SearchResult):
        app_label, model_name = instance.app_label, instance.model_name
    else:
        meta = instance._meta
        if getattr(instance, '_deferred', False):
            meta = get_proxied_model(meta)._meta
        app_label, model_name = meta.app_label, meta.module_name

    return app_label, model_name

def get_deferred_fields(instance):
    """
    Return a list of all deferred field for the given instance.
    Deferred fields are ones in "deferred" or not in "only" or parts
    of a queryset
    """
    return [field.attname for field in instance._meta.fields if isinstance(instance.__class__.__dict__.get(field.attname), DeferredAttribute)]


# BELOW : https://github.com/andymccurdy/django-tips-and-tricks/blob/master/model_update.py

import operator

from django.db.models.expressions import F, ExpressionNode

EXPRESSION_NODE_CALLBACKS = {
    ExpressionNode.ADD: operator.add,
    ExpressionNode.SUB: operator.sub,
    ExpressionNode.MUL: operator.mul,
    ExpressionNode.DIV: operator.div,
    ExpressionNode.MOD: operator.mod,
    ExpressionNode.AND: operator.and_,
    ExpressionNode.OR: operator.or_,
    }

class CannotResolve(Exception):
    pass

def _resolve(instance, node):
    if isinstance(node, F):
        return getattr(instance, node.name)
    elif isinstance(node, ExpressionNode):
        return _resolve(instance, node)
    return node

def resolve_expression_node(instance, node):
    op = EXPRESSION_NODE_CALLBACKS.get(node.connector, None)
    if not op:
        raise CannotResolve
    runner = _resolve(instance, node.children[0])
    for n in node.children[1:]:
        runner = op(runner, _resolve(instance, n))
    return runner

def update(instance, **kwargs):
    "Atomically update instance, setting field/value pairs from kwargs"
    # fields that use auto_now=True should be updated corrected, too!
    for field in instance._meta.fields:
        if hasattr(field, 'auto_now') and field.auto_now and field.name not in kwargs:
            kwargs[field.name] = field.pre_save(instance, False)

    rows_affected = instance.__class__._default_manager.filter(pk=instance.pk).update(**kwargs)

    # apply the updated args to the instance to mimic the change
    # note that these might slightly differ from the true database values
    # as the DB could have been updated by another thread. callers should
    # retrieve a new copy of the object if up-to-date values are required
    for k,v in kwargs.iteritems():
        if isinstance(v, ExpressionNode):
            v = resolve_expression_node(instance, v)
        setattr(instance, k, v)

    # If you use an ORM cache, make sure to invalidate the instance!
    #cache.set(djangocache.get_cache_key(instance=instance), None, 5)
    return rows_affected


# BELOW : http://djangosnippets.org/snippets/1949/

import gc

def queryset_iterator(queryset, chunksize=1000):
    '''''
    Iterate over a Django Queryset ordered by the primary key

    This method loads a maximum of chunksize (default: 1000) rows in it's
    memory at the same time while django normally would load all rows in it's
    memory. Using the iterator() method only causes it to not preload all the
    classes.

    Note that the implementation of the iterator does not support ordered query sets.
    '''
    pk = 0
    last_pk = queryset.order_by('-pk')[0].pk
    queryset = queryset.order_by('pk')
    while pk < last_pk:
        for row in queryset.filter(pk__gt=pk)[:chunksize]:
            pk = row.pk
            yield row
        gc.collect()
