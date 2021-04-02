import micropython

@micropython.asm_thumb
def _decompress(r0, r1):  # pointer to input and output buffer
    ldrh(r2, [r0, 0]) # read the size of the output buffer
    add(r0, 2)

    label(LOOP)
    cmp (r2,0)
    ble(EXIT_LOOP)

    ldrb (r5, [r0, 0])  # data[i]
    add (r0,1)
    cmp (r5, 0xC0)  # if data[i]>=0xC0
    blt (ELSE)
    label (THEN)

    mov(r3, r5)
    sub(r3, 0xC0) # r3 loop to do
    sub(r2, r2, r3)
    ldrb (r4, [r0, 0])  # data[i+1]
    add(r0,1)
    label(RANGE_LOOP)
    strb (r4, [r1, 0])
    add(r1,1)

    sub(r3, r3, 1)
    bgt(RANGE_LOOP)
    b(LOOP) # optimization; remove this line if adding code after the if... original line was: b(ENDIF)

    label(ELSE)

    strb(r5, [r1, 0])
    add(r1, 1)
    sub(r2, 1)

    label(ENDIF)
    b(LOOP)
    label(EXIT_LOOP)
    mov (r0, r2)


def _compress(data, ret, len_data):
    ptr : int = 2
    pre_b : int = data[0]
    cnt : int = 1

    for b in data[1:]:
        if ptr>=len_data:
            ret[0] = 0xff
            ret[1] = 0xff
            for ptr in range(len_data):
                ret[2+ptr] = data[ptr]
            return 2+len_data
        
        if b!=pre_b or cnt==0x3F:
            if cnt>1 or pre_b>=0xC0:
                val : int = 0xC0 + cnt
                ret[ptr] = val ; ptr += 1
            ret[ptr] = pre_b ; ptr += 1
            pre_b = b
            cnt = 1
        else:
            cnt += 1
    if cnt>1 or pre_b>=0xC0:
        val : int = 0xC0 + cnt
        ret[ptr] = val ; ptr += 1
    ret[ptr] = pre_b ; ptr += 1

    return ptr


@micropython.asm_thumb 
def _compress_asm(r0,r1,r2):
    push({r0,r1,r2})
    
    add(r1,2)
    
    mov(r6, r2)
    
    ldrb(r3, [r0,0])  # pre_b = data[0]
    add(r0, 1)
    sub(r2, 1)
    mov(r4, 1)  # cnt = 1
    
    label (LOOP)
    
    ldrb(r5, [r0,0])  # b
    add(r0, 1)
    sub(r2, 1)
    
    cmp(r6, 3)  # r6 keep count of how many bytes are written in the output buffer
    bge(SKIP_UNCOMPRESSED)
    pop({r0,r1,r2})
    mov(r3, r2)
    add(r3, 2)
    mov(r4, 0xFF)
    strb(r4, [r1, 0])
    strb(r4, [r1, 1])
    add(r1,2)
    
    label(UNCOMPRESSED_LOOP)
    cmp(r2,0)
    beq(EXIT)
    sub(r2,1)
    ldrb(r4, [r0, 0])
    strb(r4, [r1, 0])
    add(r0,1)
    add(r1,1)
    b(UNCOMPRESSED_LOOP)
        
    label(SKIP_UNCOMPRESSED)    

    # if b!=pre_b or cnt==0x3F:
    cmp(r3,r5)
    bne(THEN_1)
    cmp(r4, 0x3F)
    bne(ELSE_1)    
    label(THEN_1)
    
    #if cnt>1 or pre_b>=0xC0:
    cmp(r4, 1)
    bgt(THEN_2)
    cmp(r3, 0xC0)
    bge(THEN_2)
    b(ENDIF_2)
    label(THEN_2)
    mov(r7, r4)
    add(r7, 0xC0)
    strb(r7,[r1,0])
    add(r1,1)
    sub(r6,1)    
    label(ENDIF_2)
    
    strb(r3,[r1,0])  # ret append pre_b
    add(r1,1)
    sub(r6,1)    
    mov(r3, r5)  # pre_b = b
    mov(r4, 1) # cnt = 1
    
    b(ENDIF_1)
    label(ELSE_1)
    add(r4, 1)  # cnt += 1
    label(ENDIF_1)
    
    cmp(r2,0)
    bgt(LOOP)
    label(END_LOOP)

    #if cnt>1 or pre_b>=0xC0:
    cmp(r4, 1)
    bgt(THEN_3)
    cmp(r3, 0xC0)
    bge(THEN_3)
    b(ENDIF_3)
    label(THEN_3)
    mov(r7, r4)
    add(r7, 0xC0)
    strb(r7,[r1,0])
    add(r1,1)
    sub(r6,1)    
    label(ENDIF_3)
    
    strb(r3,[r1,0])  # ret append pre_b
    add(r1,1)
    sub(r6,1)    

    mov(r3, r1)
    pop({r0,r1,r2})
    sub(r3, r3, r1)
    label(EXIT)
    mov(r0, r3)
    

def compress_python(data : bytes) -> bytes:
    """
    Compress a bytearray (max 65534 bytes) to another one.

    The first 16bit are little endian encoding of the lenght of the data.

    This is needed later for the decompression algorith to know how much to allocate.

    If the compressed version is bigger than the original data buffer (with RLE it can happen)
        it will return 0xffff as 16 bit lenght, that means "not compressed",
        followed by the original data
    """
    assert 0<len(data)<65535
    len_data = len(data)
    ret = bytearray(2+len_data)
    ret[0] = len_data & 0x00ff
    ret[1] = (len_data & 0xff00) >> 8
    ptr = _compress(data, ret, len_data)

    return ret[:ptr]

def compress(data : bytes) -> bytes:
    """
    Compress a bytearray (max 65534 bytes) to another one.

    The first 16bit are little endian encoding of the lenght of the data.

    This is needed later for the decompression algorith to know how much to allocate.

    If the compressed version is bigger than the original data buffer (with RLE it can happen)
        it will return 0xffff as 16 bit lenght, that means "not compressed",
        followed by the original data
    """
    assert 0<len(data)<65535
    len_data = len(data)
    ret = bytearray(2+len_data)
    ret[0] = len_data & 0x00ff
    ret[1] = (len_data & 0xff00) >> 8
    ptr = _compress_asm(data, ret, len_data)

    return ret[:ptr]


#@micropython.native
def decompress(data : bytes) -> bytes:
    buff_size : int = data[0] + (data[1] << 8)
    if buff_size == 0xffff:
        return data[2:]
    ret = bytearray(buff_size)
    _decompress(data, ret)
#    The following commented code is the python equivalent of the _decompress function call.
#    ptr : int = 0
#    i : int = 2
#    while i < len(data):
#        if data[i]>=0xC0:
#            for j in range(data[i]-0xC0):
#                ret[ptr+j] = data[i+1]
#            ptr += j + 1
#            i+=2
#        else:
#            ret[ptr] = data[i]
#            ptr += 1
#            i+=1

    return ret

def tests():
    assert compress(b'aaaabbbbp') == b'\t\x00\xc4a\xc4bp'
    assert compress(b'aaaabbbbppp') == b'\x0b\x00\xc4a\xc4b\xc3p'
    assert b'aaaaap' == decompress(compress(b'aaaaap'))
    from random import randint
    rand = bytearray(randint(10, 255))
    for i in range(len(rand)):
        rand[i] = randint(0, 255)
    cdata = compress(rand)
    try:       
        assert decompress(cdata)==rand
    except AssertionError as e:
        print(rand)
        print(cdata)
        raise e


#assert b'aaaaa\xc0bbbb\xc1' == decompress(compress(b'aaaaa\xc0bbbb\xc1'))
#assert compress(b'aaaabbbbppp') == b'\x0b\x00\xc4a\xc4b\xc3p'
#assert compress(b'aaaabbbbp') == b'\t\x00\xc4a\xc4bp'
#for _ in range(2000):
#    tests()
#print('OK')