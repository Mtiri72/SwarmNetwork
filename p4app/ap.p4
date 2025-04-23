/* -*- P4_16 -*- */
#include <core.p4>
#include <v1model.p4>

#define PKT_INSTANCE_TYPE_NORMAL 0
#define PKT_INSTANCE_TYPE_INGRESS_CLONE 1
#define PKT_INSTANCE_TYPE_EGRESS_CLONE 2

const bit<16> TYPE_IPV4 = 0x0800;
const bit<16> TYPE_ARP  = 0x0806;


// ARP RELATED CONST VARS
const bit<16> ARP_HTYPE = 0x0001; //Ethernet Hardware type is 1
const bit<16> ARP_PTYPE = TYPE_IPV4; //Protocol used for ARP is IPV4
const bit<8>  ARP_HLEN  = 6; //Ethernet address size is 6 bytes
const bit<8>  ARP_PLEN  = 4; //IP address size is 4 bytes
const bit<16> ARP_REQ = 1; //Operation 1 is request
const bit<16> ARP_REPLY = 2; //Operation 2 is reply


/*************************************************************************
*********************** H E A D E R S  ***********************************
*************************************************************************/

typedef bit<9>  egressSpec_t;
typedef bit<48> macAddr_t;
typedef bit<32> ip4Addr_t;

typedef bit<16> switchID_t;
typedef bit<48> ingress_t;
typedef bit<48> egress_t;
typedef bit<32> hoplatency_t;
typedef bit<16> flow_id_t;
typedef bit<16> cpu_t;
typedef bit<32> geo_lalitude_t;
typedef bit<32> geo_longitude_t;
typedef bit<32> geo_altitude_t;
typedef bit<32> antenna_power_t;
//typedef bit<24> padding_field_t;

header ethernet_t {
    macAddr_t dstMac;
    macAddr_t srcMac;
    bit<16>   etherType;
}

header ipv4_t {
    bit<4>    version;
    bit<4>    ihl;
    bit<6>    dscp;
    bit<2>    ecn;
    bit<16>   totalLen;
    bit<16>   identification;
    bit<3>    flags;
    bit<13>   fragOffset;
    bit<8>    ttl;
    bit<8>    protocol;
    bit<16>   hdrChecksum;
    ip4Addr_t srcIP;
    ip4Addr_t dstIP;
}

header arp_t {
  bit<16>   h_type;
  bit<16>   p_type;
  bit<8>    h_len;
  bit<8>    p_len;
  bit<16>   op_code;
  macAddr_t src_mac;
  ip4Addr_t src_ip;
  macAddr_t dst_mac;
  ip4Addr_t dst_ip;
  }


header udp_t {
    bit<16> src_port;
    bit<16> dst_port;
    bit<16> length_;
    bit<16> checksum;
}

/* INT Header; Might not be used */
header switch_int_t {
    switchID_t       swid;            // 16 bit
    cpu_t            cpu_value;       // 16 bits
    geo_lalitude_t   geo_lalitude;    // 32 bits
    geo_longitude_t  geo_longitude;   // 32 bits
    geo_altitude_t   geo_altitude;    // 32 bits
    antenna_power_t  antenna_power;   // 32 bits

}

struct metadata {
    // bit<8> id_src;
    // bit<8> id_dst;
    }

struct headers {
    ethernet_t         ethernet;
    arp_t              arp;
    ipv4_t             ipv4;
}


/*************************************************************************
*********************** P A R S E R  ***********************************
*************************************************************************/

parser MyParser(packet_in packet,
                out headers hdr,
                inout metadata meta,
                inout standard_metadata_t standard_metadata) {

    state start {
        transition parse_ethernet;
    }

    state parse_ethernet {
        packet.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            TYPE_IPV4: parse_ipv4;
            TYPE_ARP: parse_arp;

            default: accept;
        }
    }
    
    state parse_arp {
      packet.extract(hdr.arp);
        transition select(hdr.arp.op_code) {
          ARP_REQ: accept;
      }
    }

    state parse_ipv4 {
        packet.extract(hdr.ipv4);
        transition accept;
    }

}


/*************************************************************************
************   C H E C K S U M    V E R I F I C A T I O N   *************
*************************************************************************/

control MyVerifyChecksum(inout headers hdr, inout metadata meta) {
    apply {  }
}


/*************************************************************************
**************  I N G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyIngress(inout headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t standard_metadata) {
     
    counter (1, CounterType.packets) mcast_counter;
    counter(32w1, CounterType.packets) unicast_counter;

    action drop() {
        mark_to_drop(standard_metadata);
        exit;
    }

    action ac_send_to_coordinator(egressSpec_t eif){
        // hdr.ethernet.srcMac = srcMac;
        // hdr.ethernet.dstMac = dstMac;
        standard_metadata.egress_spec = eif;
    }

    /*
    Merge with swarm ACL: 
        this table plays the role of checking of blacklisted nodes.
    */
    table tb_swarm_control {
        key = {
            standard_metadata.ingress_port: exact;
            hdr.ipv4.dstIP: exact;
            // hdr.tcp.dst_port: ternary;
        }
        actions = {NoAction; ac_send_to_coordinator; drop;}
    }




   // -------------------------------------------------------------//
   // --------- M U L T I C A S T  H A N D L I N G ----------------//

    action ac_set_mcast_grp (bit<16> mcast_grp) {

        standard_metadata.mcast_grp = mcast_grp;
        // See Section 6.4 of RFC 1112
        // hdr.ethernet.dstMac = 0xffffffffffff;

        // The P4_16 |-| operator is a saturating operation, meaning
        // that since the operands are unsigned integers, the result
        // cannot wrap around below 0 back to the maximum possible
        // value, the way the result of the - operator can.
        hdr.ipv4.ttl = hdr.ipv4.ttl |-| 1;
    } 

    table tb_ipv4_mc_route_lookup {
        key = {
            hdr.ipv4.dstIP: lpm;
        }
        actions = {
            ac_set_mcast_grp;
            drop;
        }
        const default_action = drop;
    }


    //------------------------------------------------------//
    //------------  I P V 4  H A N D L I N G   -------------//

    /* Experimental; forward WITH setting MAC address */
    action ac_ipv4_forward_mac(egressSpec_t port, macAddr_t dMac) {
        standard_metadata.egress_spec = port;
        // hdr.ethernet.srcMac = hdr.ethernet.dstMac;
        hdr.ethernet.dstMac = dMac;
        hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
    }

    action ac_ipv4_forward_mac_from_dst_ip(egressSpec_t port) {
        standard_metadata.egress_spec = port;
        // hdr.ethernet.srcMac = hdr.ethernet.dstMac;
        hdr.ethernet.dstMac = (bit<48>) hdr.ipv4.dstIP;
        hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
    }

    /* Experimental; forward WTHOUT setting MAC address */
    action ac_ipv4_forward(egressSpec_t port) {
        standard_metadata.egress_spec = port;
        hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
    }

    table tb_ipv4_lpm {
        key = {            
            hdr.ipv4.dstIP: lpm;
            // hdr.udp.dst_port: ternary;
        }
        actions = {
            ac_ipv4_forward;
            ac_ipv4_forward_mac;
            ac_ipv4_forward_mac_from_dst_ip;
            drop;
            NoAction;
        }
        size = 1024;
        default_action = NoAction();
    }

    //------------------------------------------------------//
    //---------------  L 2  H A N D L I N G  ---------------//

    action ac_l2_forward(egressSpec_t eif ){
        standard_metadata.egress_spec = eif;
    }

    action ac_l2_broadcast(bit<16> mcast_grp ){
        mcast_counter.count(0);
        standard_metadata.mcast_grp = mcast_grp;
    }

    table tb_l2_forward {
        key = {
            hdr.ethernet.dstMac             :   ternary;
        } 
        actions = {
            ac_l2_forward;
            ac_l2_broadcast;
            drop;
            NoAction;
        }
        size = 1024;
        default_action = NoAction();
        counters = mcast_counter;
    }   
    


    /* Merged with Swarm ACL:
        Added tables to check IDs of source and destination nodes
     */

//     action get_swarm_id_src(bit<8> id){
//         meta.id_src = id; 
//     }
//     action get_swarm_id_dst(bit<8> id){
//         meta.id_dst= id; 
//     }

// // Check the swarm id of src host
//     table tb_check_swarm_id_src{
//         key = {
//             hdr.ipv4.srcIP: lpm;
//         }
//         actions = {
//             get_swarm_id_src;
//             drop;
//         }
//         default_action = drop();
        
//     }



    // table tb_check_dst_mac{
    //     key = {
    //         hdr.ethernet.dstMac: exact;
    //         standard_metadata.ingress_port: exact;
    //     }
    //     actions = {
    //         NoAction;
    //         drop;
    //     }
    //     default_action = drop();
        
    // }

    //------------------------------------------------------//
    //------ I N G R E S S  P R O C E S S I N G ------------//
    apply {
        // if (!tb_check_dst_mac.apply().hit ){
        //     exit;
        // }

        if (hdr.ethernet.etherType == TYPE_ARP && hdr.arp.op_code == ARP_REQ ) {
            //update operation code from request to reply
            hdr.arp.op_code = ARP_REPLY;
            
            //reply's dst_mac is the request's src mac
            hdr.arp.dst_mac = hdr.arp.src_mac;
            
            //reply's dst_ip is the request's src ip
            hdr.arp.src_mac = (bit<48>) hdr.arp.dst_ip;

            //reply's src ip is the request's dst ip
            hdr.arp.src_ip = hdr.arp.dst_ip;

            //update ethernet header
            hdr.ethernet.dstMac = hdr.ethernet.srcMac;
            hdr.ethernet.srcMac = (bit<48>) hdr.arp.dst_ip;

            //send it back to the same port
            standard_metadata.egress_spec = standard_metadata.ingress_port;
            exit;
        } 
        
        if (tb_l2_forward.apply().hit);

        if (hdr.ipv4.isValid()) {
            // if(tb_swarm_control.apply().hit){
            //     exit;
            // }
            // tb_check_swarm_id_src.apply();
            // tb_check_swarm_id_dst.apply();
            // if (meta.id_dst != meta.id_src){
            //     drop();
            // }
            if( !tb_ipv4_lpm.apply().hit){
                tb_ipv4_mc_route_lookup.apply();
            }
        }
 

    } // END OF APPLY BLOCK
    
} // END OF INGRESS BLOCK


/*************************************************************************
****************  E G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyEgress(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t standard_metadata) {
        apply{
            // log_msg("ingress_port: {}, egress_port: {}", {standard_metadata.ingress_port, standard_metadata.egress_port });

            if (standard_metadata.ingress_port == standard_metadata.egress_port && hdr.ethernet.etherType != TYPE_ARP) {
                mark_to_drop(standard_metadata);
            }

        }
}

/*************************************************************************
*************   C H E C K S U M    C O M P U T A T I O N   **************
*************************************************************************/

control MyComputeChecksum(inout headers hdr, inout metadata meta) {
     apply {
        update_checksum(
            hdr.ipv4.isValid(),
            { hdr.ipv4.version,
              hdr.ipv4.ihl,
              hdr.ipv4.dscp,
              hdr.ipv4.ecn,
              hdr.ipv4.totalLen,
              hdr.ipv4.identification,
              hdr.ipv4.flags,
              hdr.ipv4.fragOffset,
              hdr.ipv4.ttl,
              hdr.ipv4.protocol,
              hdr.ipv4.srcIP,
              hdr.ipv4.dstIP },
            hdr.ipv4.hdrChecksum,
            HashAlgorithm.csum16);
    }
}

/*************************************************************************
***********************  D E P A R S E R  *******************************
*************************************************************************/

control MyDeparser(packet_out packet, in headers hdr) {
    apply {
        packet.emit(hdr.ethernet);
        packet.emit(hdr.arp);
        packet.emit(hdr.ipv4);
        // packet.emit(hdr.udp);
        // packet.emit(hdr.shim);
        // packet.emit(hdr.int_header);
        // packet.emit(hdr.sw_data);
        // packet.emit(hdr.sw_traces);
    }
}

/*************************************************************************
***********************  S W I T C H  *******************************
*************************************************************************/

V1Switch(
MyParser(),
MyVerifyChecksum(),
MyIngress(),
MyEgress(),
MyComputeChecksum(),
MyDeparser()
) main;
